"""
Order status state machine.

The order lifecycle is:

    pending_payment -> paid -> ready_for_pickup -> picked_up
                |          |           |
                v          v           v
             cancelled  cancelled  cancelled          (any of the three,
                |          |           |                also -> expired)
                v          v           v
             expired    expired    expired

`picked_up`, `cancelled` and `expired` are terminal: nothing transitions
out of them. This module only knows the *graph* (which transitions are
legal) — it has no DB dependency. The one place that actually applies a
transition is `Repository._transition_order` in app/database.py, which:
  1. loads the order and its current `OrderState`,
  2. calls `assert_valid_transition` here (raises `InvalidOrderTransition`
     if the jump isn't a valid single hop — no skipping states),
  3. writes the new state,
  4. fires the transition's side effects — see app/order_events.py
     (notification, review unlock, ...).
"""
from __future__ import annotations

from typing import Dict, FrozenSet

from .schemas import OrderState

# Adjacency list: for each state, the set of states reachable in one valid
# transition. `pending_payment` -> `ready_for_pickup` directly, or
# `paid` -> `picked_up` directly, are deliberately absent: no skipping a
# step of the lifecycle, even toward a state that's otherwise reachable.
ORDER_TRANSITIONS: Dict[OrderState, FrozenSet[OrderState]] = {
    OrderState.PENDING_PAYMENT: frozenset({OrderState.PAID, OrderState.CANCELLED, OrderState.EXPIRED}),
    OrderState.PAID: frozenset({OrderState.READY_FOR_PICKUP, OrderState.CANCELLED, OrderState.EXPIRED}),
    OrderState.READY_FOR_PICKUP: frozenset({OrderState.PICKED_UP, OrderState.CANCELLED, OrderState.EXPIRED}),
    OrderState.PICKED_UP: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}

# States from which stock reserved at checkout still needs restoring if the
# order never makes it to `picked_up` (cancellation or expiry) — i.e.
# every non-terminal state.
RESTOCKABLE_STATES: FrozenSet[OrderState] = frozenset(
    {OrderState.PENDING_PAYMENT, OrderState.PAID, OrderState.READY_FOR_PICKUP}
)


class InvalidOrderTransition(ValueError):
    """Raised when a requested transition isn't a valid single hop in the
    order state machine (a skipped step, a move out of a terminal state,
    or a no-op). A `ValueError` subclass so existing `except ValueError`
    call sites keep working; callers that want the richer detail (to shape
    a 409 message) can catch this specifically instead."""

    def __init__(self, current: OrderState, target: OrderState):
        self.current = current
        self.target = target
        super().__init__(
            f"Impossibile passare l'ordine da '{current.value}' a '{target.value}': "
            "non è una transizione valida."
        )


def assert_valid_transition(current: OrderState, target: OrderState) -> None:
    """Raises `InvalidOrderTransition` unless `target` is directly
    reachable from `current` in the graph above."""
    if target not in ORDER_TRANSITIONS.get(current, frozenset()):
        raise InvalidOrderTransition(current, target)
