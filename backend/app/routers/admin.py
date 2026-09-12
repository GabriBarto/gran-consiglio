"""
Admin-only endpoints. Currently just shop license-status moderation: list
shops (optionally filtered by review status) and approve/reject one.

There is no public way to become an admin (see UserRole.ADMIN in
schemas.py) — admin accounts only exist as seeded fake data for now.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..database import User, db, to_public_shop
from ..dependencies import require_admin
from ..schemas import AdminShopReview, LicenseStatus, ShopLicenseStatusUpdate, ShopPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/shops", response_model=List[AdminShopReview])
def list_shops_for_review(
    review_status: Optional[LicenseStatus] = Query(
        None, alias="status", description="Filtra per stato (pending_review/approved/rejected)"
    ),
    admin: User = Depends(require_admin),
) -> List[AdminShopReview]:
    shops = db.list_shops()
    if review_status:
        shops = [s for s in shops if s.license_status == review_status]
    shops.sort(key=lambda s: s.created_at)

    reviews = []
    for shop in shops:
        vendor = db.get_by_id(shop.vendor_id)
        reviews.append(
            AdminShopReview(
                **to_public_shop(shop).model_dump(),
                vendor_username=vendor.username if vendor else "(utente eliminato)",
                vendor_email=vendor.email if vendor else "n/d",
            )
        )
    return reviews


@router.patch("/shops/{shop_id}/license-status", response_model=ShopPublic)
def set_shop_license_status(
    shop_id: str,
    payload: ShopLicenseStatusUpdate,
    admin: User = Depends(require_admin),
) -> ShopPublic:
    shop = db.get_shop(shop_id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")

    shop.license_status = payload.status
    db.save_shop(shop)

    # Keep the owning vendor's account-level license.status (set at
    # registration / upgrade-to-vendor time, see routers/auth.py and
    # routers/users.py) in sync: it's the same real-world review,
    # surfaced in two places for now until shops fully replace that field.
    vendor = db.get_by_id(shop.vendor_id)
    if vendor and vendor.license:
        vendor.license.status = payload.status
        db.save(vendor)

    return to_public_shop(shop)
