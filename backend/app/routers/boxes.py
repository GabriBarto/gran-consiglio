"""
Box ("surprise bag") endpoints — the Too-Good-To-Go-style core of the app:
vendor CRUD on their own shop's boxes, and public browsing of a shop's
boxes for customers. See backend/db/projectwork_en_v2.sql `box` table and
app/db/models.py::BoxRow.

Registered without its own prefix (routes are full paths below) since it
mixes vendor-only `/shops/me/boxes...` routes with the public
`/shops/{shop_id}/boxes` one — same pattern, same router as shops.py; kept
in a separate module because "box" is its own resource with its own CRUD,
not because the URL space is different.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from ..database import Box, User, db, to_public_box
from ..dependencies import require_vendor
from ..schemas import BoxPublic, BoxRequest, LicenseStatus

router = APIRouter(tags=["boxes"])


def _my_shop_or_404(vendor: User):
    shop = db.get_shop_by_vendor(vendor.id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Non hai ancora registrato un negozio.")
    return shop


def _own_box_or_404(vendor: User, box_id: str) -> Box:
    shop = _my_shop_or_404(vendor)
    box = db.get_box(box_id)
    if not box or box.shop_id != shop.id:
        # 404, not 403: don't confirm to a vendor that a box id belongs to
        # someone else's shop.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Box non trovata.")
    return box


# ---------------------------------------------------------------------------
# Vendor: manage their own shop's boxes
#
# Registered before the public GET /shops/{shop_id}/boxes below, same
# literal-before-parameterized ordering as GET /shops/me vs GET
# /shops/{shop_id} in shops.py — otherwise "me" would be swallowed by
# {shop_id}.
# ---------------------------------------------------------------------------

@router.get("/shops/me/boxes", response_model=List[BoxPublic])
def list_my_boxes(vendor: User = Depends(require_vendor)) -> List[BoxPublic]:
    shop = _my_shop_or_404(vendor)
    return [to_public_box(b) for b in db.list_boxes_by_shop(shop.id)]


@router.post("/shops/me/boxes", response_model=BoxPublic, status_code=status.HTTP_201_CREATED)
def create_box(payload: BoxRequest, vendor: User = Depends(require_vendor)) -> BoxPublic:
    shop = _my_shop_or_404(vendor)
    box = db.create_box(
        shop_id=shop.id,
        name=payload.name,
        price=payload.price,
        description=payload.description,
        category=payload.category,
        allergens=payload.allergens,
        max_boxes=payload.max_boxes,
        pickup_window_start=payload.pickup_window_start,
        pickup_window_end=payload.pickup_window_end,
        expire_at=payload.expire_at,
    )
    return to_public_box(box)


@router.put("/shops/me/boxes/{box_id}", response_model=BoxPublic)
def update_box(box_id: str, payload: BoxRequest, vendor: User = Depends(require_vendor)) -> BoxPublic:
    box = _own_box_or_404(vendor, box_id)
    box.name = payload.name
    box.price = payload.price
    box.description = payload.description
    box.category = payload.category
    box.allergens = payload.allergens
    box.max_boxes = payload.max_boxes
    box.pickup_window_start = payload.pickup_window_start
    box.pickup_window_end = payload.pickup_window_end
    box.expire_at = payload.expire_at
    db.save_box(box)
    return to_public_box(box)


@router.delete("/shops/me/boxes/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_box(box_id: str, vendor: User = Depends(require_vendor)) -> None:
    box = _own_box_or_404(vendor, box_id)
    try:
        db.delete_box(box.id)
    except IntegrityError:
        # order_item.boxId has no ON DELETE CASCADE (see app/db/models.py):
        # a box that's ever been ordered can't be deleted, to keep past
        # orders' line items intact. Surface that as a clean 409 instead
        # of a raw 500.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Non puoi eliminare questa box: ha già degli ordini associati. "
            "Puoi comunque azzerarne la quantità disponibile modificandola.",
        )


# ---------------------------------------------------------------------------
# Public: browse a shop's boxes (customer-facing — reached by tapping a
# shop in search results, see GET /shops)
# ---------------------------------------------------------------------------

@router.get("/shops/{shop_id}/boxes", response_model=List[BoxPublic])
def list_shop_boxes(shop_id: str) -> List[BoxPublic]:
    shop = db.get_shop(shop_id)
    if not shop or shop.license_status != LicenseStatus.APPROVED:
        # Same as GET /shops/{shop_id}: hide the existence of an unapproved
        # shop's boxes from everyone (there's no owner/admin bypass here —
        # a vendor manages their own boxes via /shops/me/boxes instead).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")
    return [to_public_box(b) for b in db.list_boxes_by_shop(shop.id)]
