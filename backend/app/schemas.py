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


class BoxRequest(BaseModel):
    """Shared shape for creating and (fully) updating one of the vendor's
    boxes. `sold_boxes` structurally has no field here at all — it's only
    ever moved by a future order/checkout flow, never set directly by the
    vendor (same reasoning as license_status not being on ShopRequest)."""

    name: str
    price: float = Field(..., gt=0)
    description: str
    category: str
    allergens: str
    max_boxes: int = Field(..., gt=0, description="Quante box di questo tipo sono disponibili in totale")
    pickup_window_start: str = Field(..., description="Formato HH:MM (24h)")
    pickup_window_end: str = Field(..., description="Formato HH:MM (24h)")
    expire_at: datetime = Field(..., description="Entro quando la box va ritirata, dopo scompare dal catalogo")

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not (2 <= len(trimmed) <= 50):  # varchar(50) in the DB
            raise ValueError("Il nome della box deve avere tra 2 e 50 caratteri.")
        return trimmed

    @field_validator("description")
    @classmethod
    def _check_description(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 250:  # varchar(250) in the DB
            raise ValueError("La descrizione è obbligatoria e non può superare 250 caratteri.")
        return trimmed

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 100:  # varchar(100) in the DB
            raise ValueError("La categoria è obbligatoria e non può superare 100 caratteri.")
        return trimmed

    @field_validator("allergens")
    @classmethod
    def _check_allergens(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 250:  # varchar(250) in the DB
            raise ValueError("Indica gli allergeni (anche 'Nessuno') — massimo 250 caratteri.")
        return trimmed

    @field_validator("pickup_window_start", "pickup_window_end")
    @classmethod
    def _check_time_format(cls, v: str) -> str:
        return _validate_hhmm(v)

    @model_validator(mode="after")
    def _check_pickup_window_order(self) -> "BoxRequest":
        if self.pickup_window_start >= self.pickup_window_end:
            raise ValueError("La fascia di ritiro deve avere un orario di inizio precedente a quello di fine.")
        return self


class BoxPublic(BaseModel):
    id: str
    shop_id: str
    name: str
    price: float
    description: str
    category: str
    allergens: str
    max_boxes: int
    sold_boxes: int
    available: int = Field(..., description="max_boxes - sold_boxes, mai negativo")
    pickup_window_start: str
    pickup_window_end: str
    expire_at: datetime
    created_at: datetime


class AdminShopPublic(ShopPublic):
    """ShopPublic plus the vendor's own account info — only exposed to
    admins reviewing the license queue (GET /admin/shops), where knowing
    *who* owns the shop is the whole point (the vendor's own create/update
    requests never see or set this)."""

    vendor_username: str
    vendor_email: str


# ---------------------------------------------------------------------------
# Cart + checkout (customer side of the box flow — see routers/cart.py)
# ---------------------------------------------------------------------------

class CartItemRequest(BaseModel):
    box_id: str
    quantity: int = Field(..., gt=0)


class CartItemQuantityUpdate(BaseModel):
    quantity: int = Field(..., gt=0)


class CartItemPublic(BaseModel):
    box_id: str
    box_name: str
    unit_price: float
    quantity: int
    subtotal: float
    # The box's *current* availability (independent of how many of it are
    # already sitting in this cart) — lets the client warn "solo 2 rimaste"
    # before checkout ever rejects it.
    available: int


class CartPublic(BaseModel):
    shop_id: str
    shop_name: str
    items: List[CartItemPublic]
    total_price: float


# ---------------------------------------------------------------------------
# Orders (created from a cart at checkout — see Repository.checkout_cart)
# ---------------------------------------------------------------------------

class OrderState(str, Enum):
    """Full order lifecycle — see app/order_state_machine.py for the valid
    transitions between these and app/order_events.py for the side effects
    each one triggers. `pending_payment` and `paid` replace the old single
    `booked` (checkout used to skip a payment step entirely);
    `ready_for_pickup` is new too, between the vendor preparing the box and
    the customer collecting it."""

    PENDING_PAYMENT = "pendingPayment"
    PAID = "paid"
    READY_FOR_PICKUP = "readyForPickup"
    PICKED_UP = "pickedUp"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderItemPublic(BaseModel):
    box_id: str
    box_name: str
    quantity: int
    unit_price: float
    subtotal: float


class OrderPublic(BaseModel):
    id: str
    shop_id: str
    shop_name: str
    total_price: float
    order_date: datetime
    state: OrderState
    pickup_window: str
    items: List[OrderItemPublic]
    # True once the order has reached 'pickedUp' — the "review unlocked"
    # signal fired by the state machine (see app/order_events.py). No
    # review-submission endpoint exists yet; this is what it'll gate on.
    review_unlocked: bool


class OrderStateUpdate(BaseModel):
    """Vendor-only transition on one of their shop's orders (see
    PATCH /shops/me/orders/{order_id}) — a customer cancels their own via
    the dedicated POST /orders/{order_id}/cancel instead, and confirms
    their own payment via POST /orders/{order_id}/pay. Only these three
    target states are ever valid to set by hand here; 'pendingPayment' and
    'paid' are reached elsewhere, and 'expired' is meant for a future
    automated job, not a manual action. Whether the *current* state
    actually allows the requested jump is enforced separately by the state
    machine (app/order_state_machine.py), not here — this only checks
    which states are settable by a vendor at all."""

    state: OrderState

    @field_validator("state")
    @classmethod
    def _check_settable(cls, v: OrderState) -> OrderState:
        settable = (OrderState.READY_FOR_PICKUP, OrderState.PICKED_UP, OrderState.CANCELLED)
        if v not in settable:
            allowed = ", ".join(f"'{s.value}'" for s in settable)
            raise ValueError(f"Stato non impostabile manualmente: solo {allowed}.")
        return v


class ShopLicenseStatusUpdate(BaseModel):
    status: LicenseStatus


# ---------------------------------------------------------------------------
# Notifications (in-app history — table exists since the original schema
# dump; app/order_events.py is the writer, see app/routers/notifications.py
# for the reader) + push device tokens (Firebase Cloud Messaging, via
# firebase-admin — see app/push_utils.py).
# ---------------------------------------------------------------------------

class NotificationType(str, Enum):
    ORDER_CONFIRMED = "orderConfirmed"
    PICKUP_REMINDER = "pickupReminder"
    BOX_AVAILABLE = "boxAvailable"
    REVIEW_REQUEST = "reviewRequest"
    ALLERGEN_FLAGGED = "allergenFlagged"
    OTHER = "other"


class NotificationPublic(BaseModel):
    id: str
    type: NotificationType
    text: str
    is_read: bool
    date: datetime


class PushPlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"


class PushTokenRequest(BaseModel):
    """Registers (or re-registers, on the same token — e.g. after a
    re-login) this device for push notifications. `token` is the *native*
    FCM/APNs token from `Notifications.getDevicePushTokenAsync()` on the
    client, not an Expo push token — see src/utils/pushNotifications.js."""

    token: str = Field(min_length=1, max_length=255)
    platform: PushPlatform
