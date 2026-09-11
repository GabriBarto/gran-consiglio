"""
Pydantic request/response models for the API.

Field names/roles mirror the shapes already used by the mock frontend layer
in src/api/auth.js (role: customer/vendor, license.status:
pending_review/approved/rejected) so wiring a real HTTP client into the app
later is a small change.
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
    # only seeded as fake data for now (see database.seed_fake_data()).
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

class LicenseInfo(BaseModel):
    file_name: str
    content_type: Optional[str] = None
    status: LicenseStatus
    uploaded_at: datetime


class UserPublic(BaseModel):
    id: str
    role: UserRole
    email: EmailStr
    username: str
    email_verified: bool
    created_at: datetime
    phone: Optional[str] = None
    shop_address: Optional[str] = None
    license: Optional[LicenseInfo] = None


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
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # 24h "HH:MM"


class Weekday(str, Enum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class DaySchedule(BaseModel):
    """One weekday's entry in a shop's opening_hours or pickup_window list.
    HH:MM strings compare correctly as plain strings (fixed-width,
    zero-padded, 24h), so no need to parse them into datetime.time just to
    check start < end."""

    day: Weekday
    closed: bool = False
    start: Optional[str] = Field(None, description="Formato HH:MM (24h)")
    end: Optional[str] = Field(None, description="Formato HH:MM (24h)")

    @field_validator("start", "end")
    @classmethod
    def _check_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not TIME_RE.match(v):
            raise ValueError("Orario non valido: usa il formato HH:MM (24h).")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "DaySchedule":
        if not self.closed:
            if not self.start or not self.end:
                raise ValueError("Specifica start ed end, oppure closed=true.")
            if self.start >= self.end:
                raise ValueError("L'orario di inizio deve precedere quello di fine.")
        return self


def _check_no_duplicate_days(schedule: List[DaySchedule]) -> List[DaySchedule]:
    days = [slot.day for slot in schedule]
    if len(days) != len(set(days)):
        raise ValueError("Non puoi avere più voci per lo stesso giorno della settimana.")
    return schedule


class ShopRequest(BaseModel):
    """Shared shape for creating and (fully) updating a shop. Notice
    license_status has no field here at all — a vendor structurally cannot
    submit it; only the admin-only ShopLicenseStatusUpdate below can change
    it (see POST /admin/shops/{id}/license-status)."""

    name: str
    address: str
    city: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    phone: str
    opening_hours: List[DaySchedule] = Field(default_factory=list)
    pickup_window: List[DaySchedule] = Field(
        default_factory=list, description="Fascia/e oraria/e di ritiro per il cliente"
    )

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not (2 <= len(trimmed) <= 100):
            raise ValueError("Il nome del negozio deve avere tra 2 e 100 caratteri.")
        return trimmed

    @field_validator("address")
    @classmethod
    def _check_address(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("L'indirizzo è obbligatorio.")
        return trimmed

    @field_validator("city")
    @classmethod
    def _check_city(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("La città è obbligatoria.")
        return trimmed

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("Numero di telefono non valido.")
        return v.strip()

    @field_validator("opening_hours", "pickup_window")
    @classmethod
    def _check_schedules(cls, v: List[DaySchedule]) -> List[DaySchedule]:
        return _check_no_duplicate_days(v)


class ShopPublic(BaseModel):
    id: str
    vendor_id: str
    name: str
    address: str
    city: str
    lat: float
    lng: float
    phone: str
    opening_hours: List[DaySchedule]
    pickup_window: List[DaySchedule]
    license_status: LicenseStatus
    created_at: datetime
    updated_at: datetime
    # Only populated by GET /shops when the request included lat/lng.
    distance_km: Optional[float] = None


class ShopSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ShopPublic]


class ShopLicenseStatusUpdate(BaseModel):
    status: LicenseStatus
