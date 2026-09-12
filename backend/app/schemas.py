"""
Pydantic request/response models for the API.

Field names/roles mirror the shapes already used by the mock frontend layer
in src/api/auth.js (role: customer/vendor, license.status:
pending_review/approved/rejected) so wiring a real HTTP client into the app
later is a small change. The app-level vocabulary here (customer/vendor,
pending_review/approved/rejected) is intentionally kept stable even though
the real DB enums differ (client/seller, pending/approved/rejected) — see
app/database.py for the mapping at the persistence boundary.
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .validation import is_valid_phone, validate_password, validate_username


class UserRole(str, Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    # Admins are never self-registered (no public endpoint creates one) —
    # only seeded as fake data for now (see backend/db/projectwork_en_v2.sql).
    # A real deployment would provision them out-of-band (DB migration,
    # internal CLI, ...), not through a public API.
    ADMIN = "admin"


class LicenseStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Public representations
# ---------------------------------------------------------------------------

class UserPublic(BaseModel):
    id: str
    role: UserRole
    email: EmailStr
    username: str
    email_verified: bool
    created_at: datetime
    # Note: phone/address/license used to live here (point 1) but the real
    # schema puts them on `store` instead (point 2) — a vendor's own shop
    # details now come from GET /shops/me, not from this response.


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class RegisterCustomerRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    password_confirm: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        error = validate_username(v)
        if error:
            raise ValueError(error)
        return v.strip()

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        error = validate_password(v)
        if error:
            raise ValueError(error)
        return v

    @model_validator(mode="after")
    def _check_match(self) -> "RegisterCustomerRequest":
        if self.password != self.password_confirm:
            raise ValueError("Le password non coincidono.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    # Either the link token, or an email+OTP pair — both flows are
    # supported (link click, or manual code entry in-app).
    token: Optional[str] = None
    email: Optional[EmailStr] = None
    otp: Optional[str] = None

    @model_validator(mode="after")
    def _check_one_of(self) -> "VerifyEmailRequest":
        if not self.token and not (self.email and self.otp):
            raise ValueError("Fornisci il token del link oppure email e codice OTP.")
        return self


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        error = validate_password(v)
        if error:
            raise ValueError(error)
        return v

    @model_validator(mode="after")
    def _check_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("Le password non coincidono.")
        return self


# ---------------------------------------------------------------------------
# Shops (vendor storefronts)
#
# Field set matches `store` in backend/db/projectwork_en_v2.sql exactly:
# a single daily openingTime, a single daily pickupWindowStart/End (not a
# per-weekday schedule — the real schema doesn't model that), a free-text
# `address` (no separate city column — see the `city` search param on
# GET /shops in routers/shops.py, which matches as a substring of address).
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # 24h "HH:MM"


def _validate_hhmm(v: str) -> str:
    if not TIME_RE.match(v):
        raise ValueError("Orario non valido: usa il formato HH:MM (24h).")
    return v


class ShopRequest(BaseModel):
    """Shared shape for creating and (fully) updating a shop. Notice
    license_status/license_url have no field here at all — a vendor
    structurally cannot submit them; only the admin-only
    ShopLicenseStatusUpdate below can change verification status (see
    PATCH /admin/shops/{id}/license-status), and license_url is set from
    the uploaded file, not typed in by the client."""

    name: str
    address: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    phone: str
    opening_time: str = Field(..., description="Formato HH:MM (24h)")
    pickup_window_start: str = Field(..., description="Formato HH:MM (24h)")
    pickup_window_end: str = Field(..., description="Formato HH:MM (24h)")

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not (2 <= len(trimmed) <= 50):  # varchar(50) in the DB
            raise ValueError("Il nome del negozio deve avere tra 2 e 50 caratteri.")
        return trimmed

    @field_validator("address")
    @classmethod
    def _check_address(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 100:  # varchar(100) in the DB
            raise ValueError("L'indirizzo è obbligatorio e non può superare 100 caratteri.")
        return trimmed

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("Numero di telefono non valido.")
        return v.strip()

    @field_validator("opening_time", "pickup_window_start", "pickup_window_end")
    @classmethod
    def _check_time_format(cls, v: str) -> str:
        return _validate_hhmm(v)

    @model_validator(mode="after")
    def _check_pickup_window_order(self) -> "ShopRequest":
        if self.pickup_window_start >= self.pickup_window_end:
            raise ValueError("La fascia di ritiro deve avere un orario di inizio precedente a quello di fine.")
        return self


class ShopPublic(BaseModel):
    id: str
    vendor_id: str
    name: str
    address: str
    lat: float
    lng: float
    phone: str
    license_url: str
    license_status: LicenseStatus
    opening_time: str
    pickup_window_start: str
    pickup_window_end: str
    # Only populated by GET /shops when the request included lat/lng.
    distance_km: Optional[float] = None


class ShopSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ShopPublic]


class ShopLicenseStatusUpdate(BaseModel):
    status: LicenseStatus
