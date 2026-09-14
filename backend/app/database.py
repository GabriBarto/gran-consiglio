"""
Persistence layer.

Users and shops are real rows in MySQL (see backend/db/projectwork_en_v2.sql
for the schema and app/db/models.py for the SQLAlchemy mapping) — this
module used to hold an in-memory fake store; it's now a thin repository
that translates between the app's Pydantic-facing vocabulary
(customer/vendor/admin, pending_review/approved/rejected, string ids) and
the DB's actual columns/enums (client/seller/admin, pending/approved/
rejected, integer ids), so every router (auth.py, users.py, shops.py,
admin.py) keeps talking to the same `db` object and dataclasses as before —
only the internals changed.

Short-lived auth bookkeeping (pending email-verification OTPs,
password-reset tokens, refresh-token revocation) is *also* real rows now
(`refresh_token`/`email_verification`/`password_reset` — see
app/db/models.py), not an in-process dict: a session or a pending
verification now survives an API restart. A high-traffic production
deployment would likely still move this specific slice to something like
Redis (it's all TTL'd, high-churn data, unlike users/shops) — see the
README — but nothing here is mock/in-memory bookkeeping anymore.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timezone
from decimal import Decimal
from typing import List, Optional

from .db.engine import get_session
from .db.models import (
    BoxRow,
    CartItemRow,
    CartRow,
    EmailVerificationRow,
    OrderItemRow,
    OrderRow,
    PasswordResetRow,
    RefreshTokenRow,
    StoreRow,
    UserRow,
)
from .schemas import (
    BoxPublic,
    CartItemPublic,
    CartPublic,
    LicenseStatus,
    OrderItemPublic,
    OrderPublic,
    ShopPublic,
    UserPublic,
    UserRole,
)
from .validation import normalize_identifier

# App-level role/status vocabulary <-> DB enum values. The app (and the
# frontend/tests built against it) keeps saying "customer"/"vendor" and
# "pending_review" — the DB, per the given schema, says "client"/"seller"
# and "pending". Translated here, at the single boundary between the two.
_APP_ROLE_TO_DB = {UserRole.CUSTOMER: "client", UserRole.VENDOR: "seller", UserRole.ADMIN: "admin"}
_DB_ROLE_TO_APP = {v: k for k, v in _APP_ROLE_TO_DB.items()}

class InsufficientAvailabilityError(Exception):
    """Raised at checkout when a cart item's quantity now exceeds the
    box's current availability (someone else bought stock, or the vendor
    lowered max_boxes, since it was added to the cart) — the whole
    checkout is rejected atomically, nothing is partially booked."""

    def __init__(self, box_name: str, available: int):
        self.box_name = box_name
        self.available = available
        super().__init__(f"{box_name}: solo {available} disponibili")

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


def _as_utc(value: datetime) -> datetime:
    """MySQL TIMESTAMP columns round-trip as naive datetimes via PyMySQL
    (the value itself is UTC — TIMESTAMP is stored/compared as UTC
    server-side — only the Python object loses the tzinfo). Everything in
    this app treats these as UTC, so reattach it here, once, rather than at
    every comparison call site."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


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


@dataclass
class Box:
    id: str
    shop_id: str
    name: str
    price: float
    description: str
    category: str
    allergens: str
    max_boxes: int
    expire_at: datetime
    created_at: datetime
    pickup_window_start: str = "18:00"
    pickup_window_end: str = "19:00"
    sold_boxes: int = 0


def _row_to_box(row: BoxRow) -> Box:
    return Box(
        id=str(row.id),
        shop_id=str(row.shop_id),
        name=row.name,
        price=float(row.price),
        description=row.description,
        category=row.category,
        allergens=row.allergens,
        max_boxes=row.max_boxes,
        sold_boxes=row.sold_boxes,
        expire_at=_as_utc(row.expire_at),
        created_at=_as_utc(row.created_at),
        pickup_window_start=_format_hhmm(row.pickup_window_start),
        pickup_window_end=_format_hhmm(row.pickup_window_end),
    )


class Repository:
    """DB-backed repository for `user`/`store`/`box`, plus DB-backed
    bookkeeping for short-lived auth tokens (see EmailVerificationRow/
    PasswordResetRow/RefreshTokenRow in app/db/models.py)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # -- email verification ------------------------------------------------
    def set_pending_verification(self, user_id: str, *, otp: str, expires_at: datetime) -> None:
        """Replaces any existing pending verification for this user (a
        resend invalidates the previous OTP, matching the old in-memory
        behavior of simply overwriting the dict entry)."""
        with get_session() as session:
            row = session.get(EmailVerificationRow, int(user_id))
            if row:
                row.otp = otp
                row.expires_at = expires_at
            else:
                session.add(EmailVerificationRow(user_id=int(user_id), otp=otp, expires_at=expires_at))

    def get_pending_verification(self, user_id: str) -> Optional[dict]:
        with get_session() as session:
            row = session.get(EmailVerificationRow, int(user_id))
            return {"otp": row.otp, "expires_at": _as_utc(row.expires_at)} if row else None

    def clear_pending_verification(self, user_id: str) -> None:
        with get_session() as session:
            row = session.get(EmailVerificationRow, int(user_id))
            if row:
                session.delete(row)

    # -- password reset ------------------------------------------------
    def set_pending_reset(self, user_id: str, *, jti: str, expires_at: datetime) -> None:
        """Replaces any existing pending reset for this user — only the
        most recently requested reset link/token is ever valid."""
        with get_session() as session:
            row = session.get(PasswordResetRow, int(user_id))
            if row:
                row.jti = jti
                row.expires_at = expires_at
            else:
                session.add(PasswordResetRow(user_id=int(user_id), jti=jti, expires_at=expires_at))

    def get_pending_reset(self, user_id: str) -> Optional[dict]:
        with get_session() as session:
            row = session.get(PasswordResetRow, int(user_id))
            return {"jti": row.jti, "expires_at": _as_utc(row.expires_at)} if row else None

    def clear_pending_reset(self, user_id: str) -> None:
        with get_session() as session:
            row = session.get(PasswordResetRow, int(user_id))
            if row:
                session.delete(row)

    # -- refresh tokens ------------------------------------------------
    def create_refresh_token(self, *, jti: str, user_id: str, expires_at: datetime) -> None:
        with get_session() as session:
            session.add(RefreshTokenRow(jti=jti, user_id=int(user_id), revoked=False, expires_at=expires_at))

    def get_refresh_token(self, jti: str) -> Optional[dict]:
        with get_session() as session:
            row = session.query(RefreshTokenRow).filter(RefreshTokenRow.jti == jti).one_or_none()
            return {"user_id": str(row.user_id), "revoked": row.revoked} if row else None

    def revoke_refresh_token(self, jti: str) -> None:
        with get_session() as session:
            row = session.query(RefreshTokenRow).filter(RefreshTokenRow.jti == jti).one_or_none()
            if row:
                row.revoked = True

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

    # -- boxes: lookups --------------------------------------------------
    def get_box(self, box_id: str) -> Optional[Box]:
        try:
            bid = int(box_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            row = session.get(BoxRow, bid)
            return _row_to_box(row) if row else None

    def list_boxes_by_shop(self, shop_id: str) -> List[Box]:
        with get_session() as session:
            rows = (
                session.query(BoxRow)
                .filter(BoxRow.shop_id == int(shop_id))
                .order_by(BoxRow.id.asc())
                .all()
            )
            return [_row_to_box(row) for row in rows]

    # -- boxes: mutations --------------------------------------------------
    def create_box(
        self,
        *,
        shop_id: str,
        name: str,
        price: float,
        description: str,
        category: str,
        allergens: str,
        max_boxes: int,
        pickup_window_start: str,
        pickup_window_end: str,
        expire_at: datetime,
    ) -> Box:
        with get_session() as session:
            row = BoxRow(
                shop_id=int(shop_id),
                name=name,
                price=price,
                description=description,
                category=category,
                allergens=allergens,
                max_boxes=max_boxes,
                sold_boxes=0,
                pickup_window_start=_parse_hhmm(pickup_window_start),
                pickup_window_end=_parse_hhmm(pickup_window_end),
                expire_at=expire_at,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return _row_to_box(row)

    def save_box(self, box: Box) -> None:
        """Updates the vendor-editable fields only — sold_boxes is
        intentionally never written here (see routers/boxes.py)."""
        with get_session() as session:
            row = session.get(BoxRow, int(box.id))
            if not row:
                return
            row.name = box.name
            row.price = box.price
            row.description = box.description
            row.category = box.category
            row.allergens = box.allergens
            row.max_boxes = box.max_boxes
            row.pickup_window_start = _parse_hhmm(box.pickup_window_start)
            row.pickup_window_end = _parse_hhmm(box.pickup_window_end)
            row.expire_at = box.expire_at

    def delete_box(self, box_id: str) -> None:
        with get_session() as session:
            row = session.get(BoxRow, int(box_id))
            if row:
                session.delete(row)

    # -- cart ---------------------------------------------------------
    def _active_cart(self, session, *, user_id: str, shop_id: str) -> Optional[CartRow]:
        return (
            session.query(CartRow)
            .filter(CartRow.user_id == int(user_id), CartRow.shop_id == int(shop_id), CartRow.status == "active")
            .one_or_none()
        )

    def _cart_public(self, session, *, shop_id: str, cart: Optional[CartRow]) -> CartPublic:
        shop = session.get(StoreRow, int(shop_id))
        items: List[CartItemPublic] = []
        if cart:
            for item in session.query(CartItemRow).filter(CartItemRow.cart_id == cart.id).all():
                box = session.get(BoxRow, item.box_id)
                if not box:  # ON DELETE CASCADE keeps this from actually happening
                    continue
                items.append(
                    CartItemPublic(
                        box_id=str(box.id),
                        box_name=box.name,
                        unit_price=float(box.price),
                        quantity=item.quantity,
                        subtotal=round(float(box.price) * item.quantity, 2),
                        available=max(box.max_boxes - box.sold_boxes, 0),
                    )
                )
        return CartPublic(
            shop_id=str(shop_id),
            shop_name=shop.name if shop else "",
            items=items,
            total_price=round(sum(i.subtotal for i in items), 2),
        )

    def get_cart(self, *, user_id: str, shop_id: str) -> CartPublic:
        with get_session() as session:
            return self._cart_public(session, shop_id=shop_id, cart=self._active_cart(session, user_id=user_id, shop_id=shop_id))

    def add_to_cart(self, *, user_id: str, shop_id: str, box_id: str, quantity: int) -> CartPublic:
        with get_session() as session:
            box = session.get(BoxRow, int(box_id))
            if not box or box.shop_id != int(shop_id):
                raise ValueError("box_not_found")

            cart = self._active_cart(session, user_id=user_id, shop_id=shop_id)
            if not cart:
                cart = CartRow(user_id=int(user_id), shop_id=int(shop_id), status="active")
                session.add(cart)
                session.flush()

            item = (
                session.query(CartItemRow)
                .filter(CartItemRow.cart_id == cart.id, CartItemRow.box_id == int(box_id))
                .one_or_none()
            )
            if item:
                item.quantity += quantity
            else:
                session.add(CartItemRow(cart_id=cart.id, box_id=int(box_id), quantity=quantity))
            session.flush()
            return self._cart_public(session, shop_id=shop_id, cart=cart)

    def set_cart_item_quantity(self, *, user_id: str, shop_id: str, box_id: str, quantity: int) -> CartPublic:
        with get_session() as session:
            cart = self._active_cart(session, user_id=user_id, shop_id=shop_id)
            item = (
                session.query(CartItemRow)
                .filter(CartItemRow.cart_id == cart.id, CartItemRow.box_id == int(box_id))
                .one_or_none()
                if cart
                else None
            )
            if not item:
                raise ValueError("item_not_found")
            item.quantity = quantity
            session.flush()
            return self._cart_public(session, shop_id=shop_id, cart=cart)

    def remove_cart_item(self, *, user_id: str, shop_id: str, box_id: str) -> CartPublic:
        with get_session() as session:
            cart = self._active_cart(session, user_id=user_id, shop_id=shop_id)
            if cart:
                item = (
                    session.query(CartItemRow)
                    .filter(CartItemRow.cart_id == cart.id, CartItemRow.box_id == int(box_id))
                    .one_or_none()
                )
                if item:
                    session.delete(item)
                    # autoflush is off (see db/engine.py) — without this,
                    # the re-query just below (in _cart_public) wouldn't
                    # see the pending delete yet.
                    session.flush()
            return self._cart_public(session, shop_id=shop_id, cart=cart)

    def clear_cart(self, *, user_id: str, shop_id: str) -> None:
        with get_session() as session:
            cart = self._active_cart(session, user_id=user_id, shop_id=shop_id)
            if cart:
                session.delete(cart)  # cascades to its items (relationship cascade)

    # -- checkout / orders ------------------------------------------------
    def checkout_cart(self, *, user_id: str, shop_id: str) -> OrderPublic:
        with get_session() as session:
            cart = self._active_cart(session, user_id=user_id, shop_id=shop_id)
            if not cart:
                raise ValueError("cart_not_found")
            cart_items = session.query(CartItemRow).filter(CartItemRow.cart_id == cart.id).all()
            if not cart_items:
                raise ValueError("cart_empty")

            # Lock and validate every box up front, before creating
            # anything: if any item is no longer available in the
            # requested quantity, the whole checkout fails atomically
            # (get_session() rolls back on any raised exception) rather
            # than partially booking the cart.
            locked_boxes: dict[int, BoxRow] = {}
            for item in cart_items:
                box = session.query(BoxRow).filter(BoxRow.id == item.box_id).with_for_update().one_or_none()
                if not box:
                    raise ValueError("box_not_found")
                available = box.max_boxes - box.sold_boxes
                if item.quantity > available:
                    raise InsufficientAvailabilityError(box.name, available)
                locked_boxes[item.box_id] = box

            # orders.pickupWindow is one varchar(20), not per-item — a cart
            # mixing boxes with different windows (e.g. a bakery's morning
            # bread and evening pastries) collapses to the widest span that
            # covers all of them, "HH:MM-HH:MM" (always well under 20
            # chars). Simple and always representable, if occasionally
            # wider than any single item's own window.
            starts = [locked_boxes[i.box_id].pickup_window_start for i in cart_items]
            ends = [locked_boxes[i.box_id].pickup_window_end for i in cart_items]
            pickup_window = f"{_format_hhmm(min(starts))}-{_format_hhmm(max(ends))}"

            order = OrderRow(
                user_id=int(user_id),
                shop_id=int(shop_id),
                total_price=0.0,
                state="booked",
                pickup_window=pickup_window,
            )
            session.add(order)
            session.flush()

            total = 0.0
            for item in cart_items:
                box = locked_boxes[item.box_id]
                box.sold_boxes += item.quantity
                unit_price = float(box.price)
                session.add(
                    OrderItemRow(order_id=order.id, box_id=box.id, quantity=item.quantity, unit_price=unit_price)
                )
                total += unit_price * item.quantity

            order.total_price = round(total, 2)
            cart.status = "completed"
            session.flush()
            return self._order_public(session, order)

    def _order_public(self, session, order: OrderRow) -> OrderPublic:
        shop = session.get(StoreRow, order.shop_id)
        items = []
        for item in session.query(OrderItemRow).filter(OrderItemRow.order_id == order.id).all():
            # No ON DELETE CASCADE on order_item.boxId (see app/db/models.py)
            # — a box that has ever been ordered can't actually be deleted,
            # so this is never None in practice.
            box = session.get(BoxRow, item.box_id)
            items.append(
                OrderItemPublic(
                    box_id=str(item.box_id),
                    box_name=box.name if box else "—",
                    quantity=item.quantity,
                    unit_price=float(item.unit_price),
                    subtotal=round(float(item.unit_price) * item.quantity, 2),
                )
            )
        return OrderPublic(
            id=str(order.id),
            shop_id=str(order.shop_id),
            shop_name=shop.name if shop else "",
            total_price=float(order.total_price),
            order_date=_as_utc(order.order_date),
            state=order.state,
            pickup_window=order.pickup_window,
            items=items,
        )

    def get_order(self, order_id: str) -> Optional[OrderPublic]:
        try:
            oid = int(order_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            order = session.get(OrderRow, oid)
            return self._order_public(session, order) if order else None

    def get_order_owner_ids(self, order_id: str) -> Optional[tuple[str, str]]:
        """(customer_user_id, shop_id) for the given order, for routers to
        run ownership checks without building the full public shape."""
        try:
            oid = int(order_id)
        except (TypeError, ValueError):
            return None
        with get_session() as session:
            order = session.get(OrderRow, oid)
            return (str(order.user_id), str(order.shop_id)) if order else None

    def list_orders_for_user(self, user_id: str) -> List[OrderPublic]:
        with get_session() as session:
            orders = (
                session.query(OrderRow)
                .filter(OrderRow.user_id == int(user_id))
                .order_by(OrderRow.order_date.desc())
                .all()
            )
            return [self._order_public(session, o) for o in orders]

    def list_orders_for_shop(self, shop_id: str) -> List[OrderPublic]:
        with get_session() as session:
            orders = (
                session.query(OrderRow)
                .filter(OrderRow.shop_id == int(shop_id))
                .order_by(OrderRow.order_date.desc())
                .all()
            )
            return [self._order_public(session, o) for o in orders]

    def cancel_order(self, order_id: str) -> OrderPublic:
        """Customer- or vendor-initiated cancellation of a still-booked
        order: restocks every item back onto its box (sold_boxes -= qty,
        floored at 0) before flipping the order to 'cancelled'."""
        with get_session() as session:
            order = session.get(OrderRow, int(order_id))
            if not order:
                raise ValueError("order_not_found")
            if order.state != "booked":
                raise ValueError("not_cancellable")
            for item in session.query(OrderItemRow).filter(OrderItemRow.order_id == order.id).all():
                box = session.query(BoxRow).filter(BoxRow.id == item.box_id).with_for_update().one_or_none()
                if box:
                    box.sold_boxes = max(box.sold_boxes - item.quantity, 0)
            order.state = "cancelled"
            session.flush()
            return self._order_public(session, order)

    def mark_order_picked_up(self, order_id: str) -> OrderPublic:
        with get_session() as session:
            order = session.get(OrderRow, int(order_id))
            if not order:
                raise ValueError("order_not_found")
            if order.state != "booked":
                raise ValueError("not_pickupable")
            order.state = "pickedUp"
            session.flush()
            return self._order_public(session, order)


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


def to_public_box(box: Box) -> BoxPublic:
    return BoxPublic(
        id=box.id,
        shop_id=box.shop_id,
        name=box.name,
        price=box.price,
        description=box.description,
        category=box.category,
        allergens=box.allergens,
        max_boxes=box.max_boxes,
        sold_boxes=box.sold_boxes,
        available=max(box.max_boxes - box.sold_boxes, 0),
        pickup_window_start=box.pickup_window_start,
        pickup_window_end=box.pickup_window_end,
        expire_at=box.expire_at,
        created_at=box.created_at,
    )
