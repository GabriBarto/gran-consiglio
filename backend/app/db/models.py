"""
SQLAlchemy ORM models mapped onto the exact tables/columns defined in
backend/db/projectwork_en_v2.sql: `user`, `store`, `box`, `cart`/`cart_item`
and `orders`/`order_item` (the tables the app's core features read/write),
`refresh_token`/`email_verification`/`password_reset` (short-lived auth
bookkeeping, persisted here instead of in-process memory so it survives an
API restart — see app/database.py), and `review`/`notification`, which
exist in the schema+seed data for future features but have no endpoints
yet.

Python attribute names favor readability (e.g. `vendor_id`, `license_url`)
while `mapped_column("dbColumnName", ...)` keeps them wired to the schema's
actual (camelCase) column names — the DDL itself is never touched from here.
"""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, TIMESTAMP, Boolean, Enum, Float, ForeignKey, Integer, String, Time, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(Enum("client", "seller", "admin", name="user_role"))
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column("password", String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    stores: Mapped[list["StoreRow"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class StoreRow(Base):
    __tablename__ = "store"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 8))
    longitude: Mapped[Decimal] = mapped_column(DECIMAL(11, 8))
    phone: Mapped[str] = mapped_column(String(20))
    license_url: Mapped[str] = mapped_column("licenseUrl", String(255))
    license_status: Mapped[str] = mapped_column(
        "verificationStatus", Enum("pending", "approved", "rejected", name="verification_status"), default="pending"
    )
    opening_time: Mapped[time] = mapped_column("openingTime", Time)
    pickup_window_start: Mapped[time] = mapped_column("pickupWindowStart", Time)
    pickup_window_end: Mapped[time] = mapped_column("pickupWindowEnd", Time)

    owner: Mapped["UserRow"] = relationship(back_populates="stores")
    boxes: Mapped[list["BoxRow"]] = relationship(back_populates="shop", cascade="all, delete-orphan")


class BoxRow(Base):
    """A vendor's "surprise bag" listing (the Too-Good-To-Go-style core of
    the app) — box/cart/orders/etc. all existed in the schema+seed data
    before any endpoint used them; this is the first one wired up."""

    __tablename__ = "box"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column("storeId", ForeignKey("store.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    price: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        "creationDate", TIMESTAMP, server_default=func.current_timestamp()
    )
    # Nullable in the schema, but the API always requires/sets it (see
    # schemas.BoxRequest) — a listing with no pickup-by deadline doesn't
    # make sense for this kind of app.
    expire_at: Mapped[Optional[datetime]] = mapped_column("expireDate", TIMESTAMP)
    max_boxes: Mapped[int] = mapped_column("maxBoxes", Integer)
    # Only ever changed by a future order/checkout flow — never written to
    # from routers/boxes.py's vendor-facing create/update.
    sold_boxes: Mapped[int] = mapped_column("soldBoxes", Integer, default=0)
    description: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(100))
    allergens: Mapped[str] = mapped_column(String(250))
    pickup_window_start: Mapped[time] = mapped_column("pickupWindowStart", Time)
    pickup_window_end: Mapped[time] = mapped_column("pickupWindowEnd", Time)

    shop: Mapped["StoreRow"] = relationship(back_populates="boxes")


class CartRow(Base):
    """A customer's cart at one particular shop — scoped to (user, store),
    not global, matching how pickup happens at one physical place. `status`
    flips to 'completed' at checkout (see Repository.checkout_cart);
    there's at most one 'active' cart per (user, store) pair, enforced in
    code, not by a DB constraint the given schema doesn't have."""

    __tablename__ = "cart"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id", ondelete="CASCADE"))
    shop_id: Mapped[int] = mapped_column("storeId", ForeignKey("store.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Enum("active", "completed", name="cart_status"), default="active")

    items: Mapped[list["CartItemRow"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItemRow(Base):
    __tablename__ = "cart_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column("cartId", ForeignKey("cart.id", ondelete="CASCADE"))
    box_id: Mapped[int] = mapped_column("boxId", ForeignKey("box.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer)

    cart: Mapped["CartRow"] = relationship(back_populates="items")


class OrderRow(Base):
    """A booked reservation, created from a cart at checkout
    (Repository.checkout_cart) — one row per (customer, shop, checkout),
    holding a price/quantity snapshot in OrderItemRow (so a later price or
    box edit never rewrites history)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id"))
    shop_id: Mapped[int] = mapped_column("storeId", ForeignKey("store.id"))
    total_price: Mapped[float] = mapped_column("totalPrice", Float)
    order_date: Mapped[datetime] = mapped_column("orderDate", TIMESTAMP, server_default=func.current_timestamp())
    state: Mapped[str] = mapped_column(
        Enum("booked", "pickedUp", "cancelled", "expired", name="order_state"), default="booked"
    )
    # A single "HH:MM-HH:MM" range, not per-item — see
    # Repository.checkout_cart for how it's derived when a cart mixes boxes
    # with different pickup windows.
    pickup_window: Mapped[str] = mapped_column("pickupWindow", String(20))

    items: Mapped[list["OrderItemRow"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItemRow(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column("orderId", ForeignKey("orders.id", ondelete="CASCADE"))
    # No ON DELETE CASCADE in the schema (RESTRICT by default): a box that
    # has ever been ordered can no longer be deleted — see routers/boxes.py,
    # which turns that DB-level IntegrityError into a clean 409.
    box_id: Mapped[int] = mapped_column("boxId", ForeignKey("box.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column("unitPrice", Float)

    order: Mapped["OrderRow"] = relationship(back_populates="items")


class RefreshTokenRow(Base):
    """One row per issued refresh token, so revocation (used at rotation —
    see routers/auth.py) survives an API restart instead of being an
    in-process dict. `jti` is the token's own claim, not a foreign key."""

    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id", ondelete="CASCADE"))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column("expiresAt", TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column("createdAt", TIMESTAMP, server_default=func.current_timestamp())


class EmailVerificationRow(Base):
    """The one active OTP for a user's pending email verification (see
    POST /auth/verify-email). Keyed by user, not autoincrement: a resend
    replaces it in place rather than accumulating rows."""

    __tablename__ = "email_verification"

    user_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    otp: Mapped[str] = mapped_column(String(6))
    expires_at: Mapped[datetime] = mapped_column("expiresAt", TIMESTAMP)


class PasswordResetRow(Base):
    """The one active password-reset token (by jti) for a user (see
    POST /auth/forgot-password / /auth/reset-password). Same one-row-per-user
    shape as EmailVerificationRow, for the same reason."""

    __tablename__ = "password_reset"

    user_id: Mapped[int] = mapped_column("userId", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    jti: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column("expiresAt", TIMESTAMP)
