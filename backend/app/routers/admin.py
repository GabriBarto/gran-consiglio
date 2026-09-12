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
from ..schemas import LicenseStatus, ShopLicenseStatusUpdate, ShopPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/shops", response_model=List[ShopPublic])
def list_shops_for_review(
    review_status: Optional[LicenseStatus] = Query(
        None, alias="status", description="Filtra per stato (pending_review/approved/rejected)"
    ),
    admin: User = Depends(require_admin),
) -> List[ShopPublic]:
    shops = db.list_shops()  # already ordered by id (creation order)
    if review_status:
        shops = [s for s in shops if s.license_status == review_status]
    return [to_public_shop(s) for s in shops]


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
    return to_public_shop(shop)
