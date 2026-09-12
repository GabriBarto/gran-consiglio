"""
Fake in-memory "database" layer.

There is no real (external) database available yet, so this module keeps
everything in process memory, seeded with a few fictitious demo accounts
(see seed_fake_data()). Swap this module for a real persistence layer
(PostgreSQL + SQLAlchemy/SQLModel, MongoDB, ...) before shipping — every
other module only talks to the `db` object below and to to_public_user(), so
the rest of the app should not need to change.

Note the license document itself is never stored here: only the metadata +
storage URL returned by storage.py (see save_license_file). The binary file
lives in the fake object store, mirroring how it would live in S3/Cloud
Storage in production.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import settings
from .schemas import DaySchedule, LicenseInfo, LicenseStatus, ShopPublic, UserPublic, UserRole, Weekday
from .validation import normalize_identifier


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class License:
    file_name: str
    content_type: Optional[str]
    storage_url: str
    status: LicenseStatus = LicenseStatus.PENDING_REVIEW
    uploaded_at: datetime = field(default_factory=utcnow)


@dataclass
class User:
    id: str
    role: UserRole
    email: str
    username: str
    password_hash: str
    created_at: datetime = field(default_factory=utcnow)
    email_verified: bool = False
    phone: Optional[str] = None
    shop_address: Optional[str] = None
    license: Optional[License] = None


@dataclass
class Shop:
    """A vendor's storefront. One-to-one with a vendor User (id ==
    vendor_id key in InMemoryDB._shop_by_vendor). license_status mirrors
    the vendor's account-level license.status (see auth.py/users.py) but
    is tracked independently here per the "shop management" requirements —
    only an admin can change it (routers/admin.py), never the vendor."""

    id: str
    vendor_id: str
    name: str
    address: str
    city: str
    lat: float
    lng: float
    phone: str
    opening_hours: List[DaySchedule] = field(default_factory=list)
    pickup_window: List[DaySchedule] = field(default_factory=list)
    license_status: LicenseStatus = LicenseStatus.PENDING_REVIEW
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


class InMemoryDB:
    """Thread-safe in-memory store standing in for the real database."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: Dict[str, User] = {}
        self._email_index: Dict[str, str] = {}     # normalized email -> id
        self._username_index: Dict[str, str] = {}  # normalized username -> id
        self._id_counter = itertools.count(1)

        self._shops: Dict[str, Shop] = {}
        self._shop_by_vendor: Dict[str, str] = {}  # vendor_id -> shop_id
        self._shop_id_counter = itertools.count(1)

        # Short-lived token/OTP bookkeeping. A real deployment would put
        # this in a cache like Redis (with native TTL) rather than memory.
        self.pending_verifications: Dict[str, dict] = {}  # user id -> {otp, expires_at}
        self.pending_resets: Dict[str, dict] = {}          # user id -> {jti}
        self.refresh_tokens: Dict[str, dict] = {}           # jti -> {user_id, revoked}

    # -- lookups --------------------------------------------------------
    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        uid = self._email_index.get(normalize_identifier(email))
        return self._users.get(uid) if uid else None

    def get_by_username(self, username: str) -> Optional[User]:
        uid = self._username_index.get(normalize_identifier(username))
        return self._users.get(uid) if uid else None

    def email_taken(self, email: str) -> bool:
        return normalize_identifier(email) in self._email_index

    def username_taken(self, username: str) -> bool:
        return normalize_identifier(username) in self._username_index

    # -- mutations --------------------------------------------------------
    def create_user(self, *, role: UserRole, email: str, username: str, password_hash: str, **extra) -> User:
        with self._lock:
            if self.email_taken(email):
                raise ValueError("email_taken")
            if self.username_taken(username):
                raise ValueError("username_taken")

            prefix = {UserRole.VENDOR: "vend", UserRole.ADMIN: "admin"}.get(role, "cust")
            user_id = f"{prefix}_{next(self._id_counter)}"
            user = User(
                id=user_id,
                role=role,
                email=email.strip(),
                username=username.strip(),
                password_hash=password_hash,
                **extra,
            )
            self._users[user_id] = user
            self._email_index[normalize_identifier(email)] = user_id
            self._username_index[normalize_identifier(username)] = user_id
            return user

    def save(self, user: User) -> None:
        with self._lock:
            self._users[user.id] = user

    # -- shops --------------------------------------------------------
    def create_shop(self, *, vendor_id: str, **fields) -> Shop:
        with self._lock:
            if vendor_id in self._shop_by_vendor:
                raise ValueError("shop_exists")
            shop_id = f"shop_{next(self._shop_id_counter)}"
            shop = Shop(id=shop_id, vendor_id=vendor_id, **fields)
            self._shops[shop_id] = shop
            self._shop_by_vendor[vendor_id] = shop_id
            return shop

    def get_shop(self, shop_id: str) -> Optional[Shop]:
        return self._shops.get(shop_id)

    def get_shop_by_vendor(self, vendor_id: str) -> Optional[Shop]:
        shop_id = self._shop_by_vendor.get(vendor_id)
        return self._shops.get(shop_id) if shop_id else None

    def save_shop(self, shop: Shop) -> None:
        with self._lock:
            shop.updated_at = utcnow()
            self._shops[shop.id] = shop

    def delete_shop(self, shop_id: str) -> None:
        with self._lock:
            shop = self._shops.pop(shop_id, None)
            if shop:
                self._shop_by_vendor.pop(shop.vendor_id, None)

    def list_shops(self) -> list[Shop]:
        return list(self._shops.values())


db = InMemoryDB()


def to_public_user(user: User) -> UserPublic:
    """Never expose the password hash (or raw storage internals) to API
    responses — mirrors toPublicUser() in the JS mock."""
    return UserPublic(
        id=user.id,
        role=user.role,
        email=user.email,
        username=user.username,
        email_verified=user.email_verified,
        created_at=user.created_at,
        phone=user.phone,
        shop_address=user.shop_address,
        license=(
            LicenseInfo(
                file_name=user.license.file_name,
                content_type=user.license.content_type,
                status=user.license.status,
                uploaded_at=user.license.uploaded_at,
            )
            if user.license
            else None
        ),
    )


def to_public_shop(shop: Shop, *, distance_km: Optional[float] = None) -> ShopPublic:
    return ShopPublic(
        id=shop.id,
        vendor_id=shop.vendor_id,
        name=shop.name,
        address=shop.address,
        city=shop.city,
        lat=shop.lat,
        lng=shop.lng,
        phone=shop.phone,
        opening_hours=shop.opening_hours,
        pickup_window=shop.pickup_window,
        license_status=shop.license_status,
        created_at=shop.created_at,
        updated_at=shop.updated_at,
        distance_km=round(distance_km, 3) if distance_km is not None else None,
    )


_WEEK_ORDER = [Weekday.MON, Weekday.TUE, Weekday.WED, Weekday.THU, Weekday.FRI, Weekday.SAT, Weekday.SUN]


def _weekly_schedule(open_time: str, close_time: str, closed_days: tuple = ()) -> list[DaySchedule]:
    """Small helper to build a full Mon-Sun DaySchedule list for seed data
    without repeating each day by hand."""
    return [
        DaySchedule(day=day, closed=True) if day in closed_days else DaySchedule(day=day, start=open_time, end=close_time)
        for day in _WEEK_ORDER
    ]


def seed_fake_data() -> None:
    """Seeds a couple of fictitious accounts for local testing/demo purposes,
    since there is no real external database yet. These are throwaway fake
    credentials, not a security concern — never do this against a real DB."""
    if db.get_by_email("cliente.demo@example.com"):
        return  # already seeded (e.g. `--reload` triggered a re-run)

    from . import security  # local import to avoid import-order surprises

    customer = db.create_user(
        role=UserRole.CUSTOMER,
        email="cliente.demo@example.com",
        username="Cliente Demo",
        password_hash=security.hash_password("Password123"),
    )
    customer.email_verified = True
    db.save(customer)

    vendor = db.create_user(
        role=UserRole.VENDOR,
        email="vivaio.rossi@example.com",
        username="Vivaio Rossi",
        password_hash=security.hash_password("Password123"),
        phone="+39 333 1234567",
        shop_address="Via delle Rose 12, Firenze",
    )
    vendor.email_verified = True
    vendor.license = License(
        file_name="licenza_vivaio_rossi.pdf",
        content_type="application/pdf",
        storage_url=f"{settings.fake_storage_base_url}/demo-licenza-approvata.pdf",
        status=LicenseStatus.APPROVED,
    )
    db.save(vendor)

    pending_vendor = db.create_user(
        role=UserRole.VENDOR,
        email="ortofrutta.bianchi@example.com",
        username="Ortofrutta Bianchi",
        password_hash=security.hash_password("Password123"),
        phone="+39 347 7654321",
        shop_address="Corso Italia 5, Bologna",
    )
    pending_vendor.email_verified = True
    pending_vendor.license = License(
        file_name="licenza_ortofrutta_bianchi.pdf",
        content_type="application/pdf",
        storage_url=f"{settings.fake_storage_base_url}/demo-licenza-pending.pdf",
        status=LicenseStatus.PENDING_REVIEW,
    )
    db.save(pending_vendor)

    admin = db.create_user(
        role=UserRole.ADMIN,
        email="admin@example.com",
        username="Admin",
        password_hash=security.hash_password("Password123"),
    )
    admin.email_verified = True
    db.save(admin)

    # Two demo shops, one per seeded vendor, so /shops and /admin/shops are
    # exercisable out of the box: one already approved (shows up in public
    # search), one still pending_review (only visible to its owner/admin,
    # and to be found in the admin review queue).
    db.create_shop(
        vendor_id=vendor.id,
        name="Vivaio Rossi",
        address="Via delle Rose 12",
        city="Firenze",
        lat=43.7696,
        lng=11.2558,
        phone=vendor.phone,
        opening_hours=_weekly_schedule("08:00", "19:30", closed_days=(Weekday.SUN,)),
        pickup_window=_weekly_schedule("18:30", "19:30", closed_days=(Weekday.SUN,)),
        license_status=LicenseStatus.APPROVED,
    )

    db.create_shop(
        vendor_id=pending_vendor.id,
        name="Ortofrutta Bianchi",
        address="Corso Italia 5",
        city="Bologna",
        lat=44.4949,
        lng=11.3426,
        phone=pending_vendor.phone,
        opening_hours=_weekly_schedule("07:30", "13:30", closed_days=(Weekday.SUN,)),
        pickup_window=_weekly_schedule("12:30", "13:30", closed_days=(Weekday.SUN,)),
        license_status=LicenseStatus.PENDING_REVIEW,
    )
