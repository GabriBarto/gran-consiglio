"""
Cart + checkout endpoints — turning the boxes a customer browses
(GET /shops/{shop_id}/boxes, see routers/boxes.py) into a booked order (see
routers/orders.py for what happens to it afterwards). A cart is scoped to
one (customer, shop) pair at a time — see `cart` in
backend/db/projectwork_en_v2.sql — matching how pickup naturally happens at
one physical shop; a customer shopping at two shops has two separate carts.

Any authenticated user can shop (no vendor-only/customer-only gate here —
there's no product reason to stop a vendor from also buying a box).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import InsufficientAvailabilityError, User, db
from ..dependencies import get_current_user
from ..schemas import CartItemQuantityUpdate, CartItemRequest, CartPublic, LicenseStatus, OrderPublic

router = APIRouter(tags=["cart"])


def _approved_shop_or_404(shop_id: str):
    """Same visibility rule as GET /shops/{shop_id} and
    GET /shops/{shop_id}/boxes: a customer can only ever interact with a
    shop that's actually approved — no owner/admin bypass needed here,
    vendors manage their own shop elsewhere."""
    shop = db.get_shop(shop_id)
    if not shop or shop.license_status != LicenseStatus.APPROVED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")
    return shop


@router.get("/shops/{shop_id}/cart", response_model=CartPublic)
def get_cart(shop_id: str, user: User = Depends(get_current_user)) -> CartPublic:
    _approved_shop_or_404(shop_id)
    return db.get_cart(user_id=user.id, shop_id=shop_id)


@router.post("/shops/{shop_id}/cart/items", response_model=CartPublic, status_code=status.HTTP_201_CREATED)
def add_cart_item(shop_id: str, payload: CartItemRequest, user: User = Depends(get_current_user)) -> CartPublic:
    _approved_shop_or_404(shop_id)
    try:
        return db.add_to_cart(user_id=user.id, shop_id=shop_id, box_id=payload.box_id, quantity=payload.quantity)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Box non trovata in questo negozio.")


@router.put("/shops/{shop_id}/cart/items/{box_id}", response_model=CartPublic)
def set_cart_item_quantity(
    shop_id: str, box_id: str, payload: CartItemQuantityUpdate, user: User = Depends(get_current_user)
) -> CartPublic:
    _approved_shop_or_404(shop_id)
    try:
        return db.set_cart_item_quantity(user_id=user.id, shop_id=shop_id, box_id=box_id, quantity=payload.quantity)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Articolo non presente nel carrello.")


@router.delete("/shops/{shop_id}/cart/items/{box_id}", response_model=CartPublic)
def remove_cart_item(shop_id: str, box_id: str, user: User = Depends(get_current_user)) -> CartPublic:
    _approved_shop_or_404(shop_id)
    return db.remove_cart_item(user_id=user.id, shop_id=shop_id, box_id=box_id)


@router.delete("/shops/{shop_id}/cart", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(shop_id: str, user: User = Depends(get_current_user)) -> None:
    _approved_shop_or_404(shop_id)
    db.clear_cart(user_id=user.id, shop_id=shop_id)


@router.post("/shops/{shop_id}/cart/checkout", response_model=OrderPublic, status_code=status.HTTP_201_CREATED)
def checkout(shop_id: str, user: User = Depends(get_current_user)) -> OrderPublic:
    """Books the customer's whole current cart for this shop as one order,
    re-validating (and locking) every item's availability first — see
    Repository.checkout_cart. Empties the cart (marks it 'completed') only
    on success; a failed checkout leaves it untouched so the customer can
    adjust quantities and retry."""
    _approved_shop_or_404(shop_id)
    try:
        return db.checkout_cart(user_id=user.id, shop_id=shop_id)
    except InsufficientAvailabilityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"'{exc.box_name}': solo {exc.available} disponibili, aggiorna la quantità nel carrello.",
        )
    except ValueError as exc:
        if str(exc) == "cart_empty":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Il carrello è vuoto.")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Carrello non trovato.")
