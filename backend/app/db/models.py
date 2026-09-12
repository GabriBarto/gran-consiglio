"""
SQLAlchemy ORM models mapped onto the exact tables/columns defined in
backend/db/projectwork_en_v2.sql (`user` and `store` — the only two tables
the app currently reads/writes; box/cart/orders/order_item/review/
notification exist in the schema+seed data for future features but have no
endpoints yet).

Python attribute names favor readability (e.g. `vendor_id`, `license_url`)
while `mapped_column("dbColumnName", ...)` keeps them wired to the schema's
actual (camelCase) column names — the DDL itself is never touched from here.
"""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import DECIMAL, TIMESTAMP, Boolean, Enum, ForeignKey, String, Time, func
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
