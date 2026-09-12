"""
Persistence layer.

Users and shops are now real rows in MySQL (see backend/db/projectwork_en_v2.sql
for the schema and app/db/models.py for the SQLAlchemy mapping) — this
module used to hold an in-memory fake store; it's now a thin repository
that translates between the app's Pydantic-facing vocabulary
(customer/vendor/admin, pending_review/approved/rejected, string ids) and
the DB's actual columns/enums (client/seller/admin, pending/approved/
rejected, integer ids), so every router (auth.py, users.py, shops.py,
admin.py) keeps talking to the same `db` object and dataclasses as before —
only the internals changed.

Short-lived, cache-like bookkeeping (pending email-verification OTPs,
password-reset tokens, refresh-token revocation) has no table in the given
schema and stays in-process memory here — a real deployment would put this
in something like Redis, not the relational DB; see the README for more on
this tradeoff.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from decimal import Decimal
from typing import Dict, List, Optional

from .db.engine import get_session
from .db.models import StoreRow, UserRow
from .schemas import LicenseStatus, ShopPublic, UserPublic, UserRole
from .validation import normalize_identifier

# App-level role/status vocabulary <-> DB enum values. The app (and the
# frontend/tests built against it) keeps saying "customer"/"vendor" and
# "pending_review" — the DB, per the given schema, says "client"/"seller"
# and "pending". Translated here, at the single boundary between the two.
_APP_ROLE_TO_DB = {UserRole.CUSTOMER: "client", UserRole.VENDOR: "seller", UserRole.ADMIN: "admin"}
_DB_ROLE_TO_APP = {v: k for k, v in _APP_ROLE_TO_DB.items()}

_APP_LICENSE_TO_DB = {
    LicenseStatus.PENDING_REVIEW: "pending",
    LicenseStatus.APPROVED: "approved",
    LicenseStatus.REJECTED: "rejected",
}
_DB_LICENSE_TO_APP = {v: k for k, v in _APP_LICENSE_TO_DB.items()}


def _parse_hhmm(value: str) -> dt_time:
    hours, minutes = value.split(":")
    return dt_time(hour=int(hours), minute=int(minutes))


def _format_hhmm(value: dt_time) -> str:
    return value.strftime("%H:%M")


@dataclass
class User:
    id: str
    role: UserRole
    email: str
    username: str
    password_hash: str
    created_at: datetime
    email_verified: bool = False


@dataclass
class Shop:
    id: str
    vendor_id: str
    name: str
    address: str
    lat: float
    lng: float
    phone: str
    license_url: str
    license_status: LicenseStatus = LicenseStatus.PENDING_REVIEW
    opening_time: str = "09:00"
    pickup_window_start: str = "18:00"
    pickup_window_end: str = "19:00"


def _row_to_user(row: UserRow) -> User:
    return User(
        id=str(row.id),
        role=_DB_ROLE_TO_APP[row.role],
        email=row.email,
        username=row.username,
        password_hash=row.password_hash,
        created_at=row.created_at,
        email_verified=bool(row.email_verified),
    )


def _row_to_shop(row: StoreRow) -> Shop:
    return Shop(
        id=str(row.id),
        vendor_id=str(row.vendor_id),
        name=row.name,
        address=row.address,
        lat=float(row.latitude),
        lng=float(row.longitude),
        phone=row.phone,
        license_url=row.license_url,
        license_status=_DB_LICENSE_TO_APP[row.license_status],
        opening_time=_format_hhmm(row.opening_time),
        pickup_window_start=_format_hhmm(row.pickup_window_start),
        pickup_window_end=_format_hhmm(row.pickup_window_end),
    )


class Repository:
    """DB-backed repository for `user`/`store`, plus in-memory bookkeeping
    for short-lived auth tokens that have no table in the given schema."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # user id -> {otp, expires_at}
        self.pending_verifications: Dict[str, dict] = {}
        # user id -> {jti}
        self.pending_resets: Dict[str, dict] = {}
        # jti -> {user_id, revoked}
        self.refresh_tokens: Dict[str, dict] = {}

    # -- users: lookups --------------------------------------------------
    def get_by_id(self, user_id: str) -> Optional[User]:
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            row = session.get(UserRow, uid)
            return _row_to_user(row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        target = normalize_identifier(email)
        with get_session() as session:
            for row in session.query(UserRow).all():
                if normalize_identifier(row.email) == target:
                    return _row_to_user(row)
        return None

    def get_by_username(self, username: str) -> Optional[User]:
        target = normalize_identifier(username)
        with get_session() as session:
            for row in session.query(UserRow).all():
                if normalize_identifier(row.username) == target:
                    return _row_to_user(row)
        return None

    def email_taken(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def username_taken(self, username: str) -> bool:
        return self.get_by_username(username) is not None

    # -- users: mutations --------------------------------------------------
    def create_user(
        self, *, role: UserRole, email: str, username: str, password_hash: str, email_verified: bool = False
    ) -> User:
        with self._lock:
            if self.email_taken(email):
                raise ValueError("email_taken")
            if self.username_taken(username):
                raise ValueError("username_taken")

            with get_session() as session:
                row = UserRow(
                    role=_APP_ROLE_TO_DB[role],
                    email=email.strip(),
                    username=username.strip(),
                    password_hash=password_hash,
                    email_verified=email_verified,
                )
                session.add(row)
                session.flush()
                session.refresh(row)
                return _row_to_user(row)

    def save(self, user: User) -> None:
        with get_session() as session:
            row = session.get(UserRow, int(user.id))
            if not row:
                return
            row.role = _APP_ROLE_TO_DB[user.role]
            row.email = user.email
            row.username = user.username
            row.password_hash = user.password_hash
            row.email_verified = user.email_verified

    # -- shops: lookups --------------------------------------------------
    def get_shop(self, shop_id: str) -> Optional[Shop]:
        try:
            sid = int(shop_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            row = session.get(StoreRow, sid)
            return _row_to_shop(row) if row else None

    def get_shop_by_vendor(self, vendor_id: str) -> Optional[Shop]:
        """A vendor may (per the seed data) own more than one store row —
        the simple "my shop" endpoints (GET/PUT/DELETE /shops/me) operate
        on their first/primary one (lowest id), deterministically."""
        try:
            vid = int(vendor_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            row = (
                session.query(StoreRow)
                .filter(StoreRow.vendor_id == vid)
                .order_by(StoreRow.id.asc())
                .first()
            )
            return _row_to_shop(row) if row else None

    def list_shops(self) -> List[Shop]:
        with get_session() as session:
            rows = session.query(StoreRow).order_by(StoreRow.id.asc()).all()
            return [_row_to_shop(row) for row in rows]

    # -- shops: mutations --------------------------------------------------
    def create_shop(
        self,
        *,
        vendor_id: str,
        name: str,
        address: str,
        lat: float,
        lng: float,
        phone: str,
        license_url: str,
        opening_time: str,
        pickup_window_start: str,
        pickup_window_end: str,
        license_status: LicenseStatus = LicenseStatus.PENDING_REVIEW,
    ) -> Shop:
        with self._lock:
            if self.get_shop_by_vendor(vendor_id):
                raise ValueError("shop_exists")

            with get_session() as session:
                row = StoreRow(
                    vendor_id=int(vendor_id),
                    name=name,
                    address=address,
                    latitude=Decimal(str(lat)),
                    longitude=Decimal(str(lng)),
                    phone=phone,
                    license_url=license_url,
                    license_status=_APP_LICENSE_TO_DB[license_status],
                    opening_time=_parse_hhmm(opening_time),
                    pickup_window_start=_parse_hhmm(pickup_window_start),
                    pickup_window_end=_parse_hhmm(pickup_window_end),
                )
                session.add(row)
                session.flush()
                session.refresh(row)
                return _row_to_shop(row)

    def save_shop(self, shop: Shop) -> None:
        with get_session() as session:
            row = session.get(StoreRow, int(shop.id))
            if not row:
                return
            row.name = shop.name
            row.address = shop.address
            row.latitude = Decimal(str(shop.lat))
            row.longitude = Decimal(str(shop.lng))
            row.phone = shop.phone
            row.license_url = shop.license_url
            row.license_status = _APP_LICENSE_TO_DB[shop.license_status]
            row.opening_time = _parse_hhmm(shop.opening_time)
            row.pickup_window_start = _parse_hhmm(shop.pickup_window_start)
            row.pickup_window_end = _parse_hhmm(shop.pickup_window_end)

    def delete_shop(self, shop_id: str) -> None:
        with get_session() as session:
            row = session.get(StoreRow, int(shop_id))
            if row:
                session.delete(row)


db = Repository()


def to_public_user(user: User) -> UserPublic:
    """Never expose the password hash to API responses."""
    return UserPublic(
        id=user.id,
        role=user.role,
        email=user.email,
        username=user.username,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


def to_public_shop(shop: Shop, *, distance_km: Optional[float] = None) -> ShopPublic:
    return ShopPublic(
        id=shop.id,
        vendor_id=shop.vendor_id,
        name=shop.name,
        address=shop.address,
        lat=shop.lat,
        lng=shop.lng,
        phone=shop.phone,
        license_url=shop.license_url,
        license_status=shop.license_status,
        opening_time=shop.opening_time,
        pickup_window_start=shop.pickup_window_start,
        pickup_window_end=shop.pickup_window_end,
        distance_km=round(distance_km, 3) if distance_km is not None else None,
    )
