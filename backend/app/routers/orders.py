"""
Order endpoints: a customer's booking history + self-service cancellation,
and the vendor side of managing bookings for their own shop (see one is
created in the first place — routers/cart.py::checkout).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import User, db
from ..dependencies import get_current_user, require_vendor
from ..order_state_machine import InvalidOrderTransition
from ..schemas import OrderPublic, OrderState, OrderStateUpdate, UserRole

router = APIRouter(tags=["orders"])


def _my_shop_or_404(vendor: User):
    shop = db.get_shop_by_vendor(vendor.id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Non hai ancora registrato un negozio.")
    return shop


def _conflict(exc: InvalidOrderTransition) -> HTTPException:
    """A transition the state machine (app/order_state_machine.py) rejects
    as an invalid jump — surfaced as 409 with the current/target states so
    the client can show something more useful than a generic error."""
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


# ---------------------------------------------------------------------------
# Customer: own booking history
# ---------------------------------------------------------------------------

@router.get("/orders", response_model=List[OrderPublic])
def list_my_orders(user: User = Depends(get_current_user)) -> List[OrderPublic]:
    return db.list_orders_for_user(user.id)


@router.get("/orders/{order_id}", response_model=OrderPublic)
def get_order(order_id: str, user: User = Depends(get_current_user)) -> OrderPublic:
    owner = db.get_order_owner_ids(order_id)
    if not owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")
    order_user_id, order_shop_id = owner

    is_owner = order_user_id == user.id
    is_admin = user.role == UserRole.ADMIN
    is_shops_vendor = False
    if user.role == UserRole.VENDOR:
        shop = db.get_shop_by_vendor(user.id)
        is_shops_vendor = shop is not None and shop.id == order_shop_id

    if not (is_owner or is_admin or is_shops_vendor):
        # 404, not 403: don't confirm to a stranger that this order id exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")
    return db.get_order(order_id)


@router.post("/orders/{order_id}/pay", response_model=OrderPublic)
def pay_order(order_id: str, user: User = Depends(get_current_user)) -> OrderPublic:
    """Confirms payment on the caller's own order (pending_payment ->
    paid). Stands in for a real payment gateway callback — see
    Repository.confirm_payment — but goes through the same state machine
    as every other transition, so it still only works from
    'pendingPayment'."""
    owner = db.get_order_owner_ids(order_id)
    if not owner or owner[0] != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")
    try:
        return db.confirm_payment(order_id)
    except InvalidOrderTransition as exc:
        raise _conflict(exc)


@router.post("/orders/{order_id}/cancel", response_model=OrderPublic)
def cancel_my_order(order_id: str, user: User = Depends(get_current_user)) -> OrderPublic:
    owner = db.get_order_owner_ids(order_id)
    if not owner or owner[0] != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")
    try:
        return db.cancel_order(order_id)
    except InvalidOrderTransition as exc:
        raise _conflict(exc)


# ---------------------------------------------------------------------------
# Vendor: bookings for their own shop
# ---------------------------------------------------------------------------

@router.get("/shops/me/orders", response_model=List[OrderPublic])
def list_shop_orders(vendor: User = Depends(require_vendor)) -> List[OrderPublic]:
    shop = _my_shop_or_404(vendor)
    return db.list_orders_for_shop(shop.id)


@router.patch("/shops/me/orders/{order_id}", response_model=OrderPublic)
def update_shop_order_state(
    order_id: str, payload: OrderStateUpdate, vendor: User = Depends(require_vendor)
) -> OrderPublic:
    """Marks a booking as ready for pickup (box prepared) or picked up
    (sale complete), or cancels it (e.g. a no-show — restocks the box,
    same as a customer's own cancellation). `payload.state` is already
    restricted to these three by OrderStateUpdate; whether the order's
    *current* state actually allows the requested one is enforced by the
    state machine (app/order_state_machine.py), surfaced here as 409."""
    shop = _my_shop_or_404(vendor)
    owner = db.get_order_owner_ids(order_id)
    if not owner or owner[1] != shop.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")

    vendor_transitions = {
        OrderState.READY_FOR_PICKUP: db.mark_ready_for_pickup,
        OrderState.PICKED_UP: db.mark_order_picked_up,
        OrderState.CANCELLED: db.cancel_order,
    }
    try:
        return vendor_transitions[payload.state](order_id)
    except InvalidOrderTransition as exc:
        raise _conflict(exc)
