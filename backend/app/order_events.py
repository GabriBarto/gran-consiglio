"""
Side effects fired when an order's state changes, plus the one fired once
at checkout (before there's a state *change* to hang off of — see
`fire_new_order_event`).

app/order_state_machine.py owns the transition *graph* (what's a valid
move); `Repository._transition_order` / `Repository.checkout_cart` in
app/database.py are the two call sites that actually write `orders.state`
and then call into this module, inside the same DB transaction, right
before it commits.

Three kinds of trigger:
  - a notification: persisted as a `notification` row (see
    app/db/models.py::NotificationRow — the table existed, unused, since
    the original schema dump) plus a best-effort push (Firebase Cloud
    Messaging — app/push_utils.py, to every device the recipient has
    registered — see PushTokenRow) and email (app/email_utils.py);
  - "review unlock": once an order reaches PICKED_UP, its notification is
    of type 'reviewRequest' and `OrderPublic.review_unlocked` flips to
    true (see Repository._order_public) — the concrete signal that a
    review is now valid to leave. Submitting one isn't built yet (no
    router uses `ReviewRow` for writes), this is the trigger it'll hang
    off of;
  - "new order", fired once at checkout — the one trigger aimed at the
    *vendor* rather than the customer, everything else above is
    customer-facing.

A notification/push/email failure never rolls back the state transition
itself — an order that's genuinely paid/ready/picked-up must not bounce
back to its previous state just because, say, SMTP or Firebase hiccuped.
Errors are logged and swallowed.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .db.models import NotificationRow, OrderRow, PushTokenRow, StoreRow, UserRow
from .email_utils import send_email
from .push_utils import send_push
from .schemas import OrderState

logger = logging.getLogger("toogood.orders")

# `notification.text` is a varchar(100) — every template here is written
# to comfortably fit a 3-digit order id, but _notification_text() still
# truncates defensively rather than let a rare long shop name 500 the
# request.
_NOTIFICATION_TITLE = "Gran Consiglio"

_NOTIFICATION_TEXT: dict[OrderState, str] = {
    OrderState.PAID: "Pagamento ricevuto per l'ordine #{order_id} da {shop_name}.",
    OrderState.READY_FOR_PICKUP: "Il tuo ordine #{order_id} da {shop_name} è pronto per il ritiro!",
    OrderState.PICKED_UP: "Ordine #{order_id} ritirato: lascia una recensione a {shop_name}!",
    OrderState.CANCELLED: "Il tuo ordine #{order_id} da {shop_name} è stato annullato.",
    OrderState.EXPIRED: "Il tuo ordine #{order_id} da {shop_name} è scaduto senza essere ritirato.",
}

_NOTIFICATION_TYPE: dict[OrderState, str] = {
    OrderState.PAID: "orderConfirmed",
    OrderState.READY_FOR_PICKUP: "pickupReminder",
    OrderState.PICKED_UP: "reviewRequest",
    OrderState.CANCELLED: "other",
    OrderState.EXPIRED: "other",
}


def _notification_text(new_state: OrderState, *, order_id: int, shop_name: str) -> str:
    template = _NOTIFICATION_TEXT[new_state]
    return template.format(order_id=order_id, shop_name=shop_name)[:100]


def _notify_user(session: Session, *, user_id: int, type_: str, text: str, email_subject: str) -> None:
    """The three legs of one notification trigger: an in-app
    `notification` row, a push to every device the user has registered
    (PushTokenRow — none is a no-op, not an error), and a best-effort
    email. Shared by every trigger below so a fourth channel, if this app
    ever gets one, only needs adding here."""
    session.add(NotificationRow(user_id=user_id, type=type_, text=text, is_read=False))

    tokens = session.query(PushTokenRow).filter(PushTokenRow.user_id == user_id).all()
    for push_token in tokens:
        try:
            send_push(token=push_token.token, title=_NOTIFICATION_TITLE, body=text)
        except Exception:  # pragma: no cover - best-effort, must never block the transition
            logger.exception("Invio push fallito per l'utente #%s (token %s...)", user_id, push_token.token[:12])

    user = session.get(UserRow, user_id)
    if user:
        try:
            send_email(to=user.email, subject=email_subject, body=text)
        except Exception:  # pragma: no cover - best-effort, must never block the transition
            logger.exception("Invio email fallito per l'utente #%s", user_id)


def fire_order_event(session: Session, *, order: OrderRow, previous_state: OrderState, new_state: OrderState) -> None:
    """Called right after `order.state` has been set to `new_state` (still
    uncommitted — same session/transaction). `previous_state` is passed
    through for hooks that only care about the target today but may need
    it later (e.g. distinguishing "cancelled from paid" vs "cancelled from
    pending_payment" for accounting). Customer-facing — see
    `fire_new_order_event` for the vendor-facing one."""
    if new_state not in _NOTIFICATION_TEXT:
        # PENDING_PAYMENT is the only state with no notification of its
        # own: it's the order's starting point, nothing has happened yet
        # from the customer's perspective.
        return

    shop = session.get(StoreRow, order.shop_id)
    text = _notification_text(new_state, order_id=order.id, shop_name=shop.name if shop else "il negozio")
    _notify_user(
        session,
        user_id=order.user_id,
        type_=_NOTIFICATION_TYPE[new_state],
        text=text,
        email_subject=f"Gran Consiglio — ordine #{order.id}",
    )


def fire_new_order_event(session: Session, *, order: OrderRow) -> None:
    """Fired once, right after checkout creates the order — notifies the
    shop's vendor a new order came in. Not a state *transition* (the order
    is born in PENDING_PAYMENT, there's no "before"), so it isn't routed
    through fire_order_event; the vendor is also a different recipient
    than every other trigger in this module (customer)."""
    shop = session.get(StoreRow, order.shop_id)
    if not shop:  # pragma: no cover - a checkout always has a real shop
        return
    text = f"Nuovo ordine #{order.id} ricevuto ({order.total_price:.2f} €)."[:100]
    _notify_user(
        session,
        user_id=shop.vendor_id,
        type_="other",  # no dedicated enum value for "new order" (see notification.type in the schema)
        text=text,
        email_subject=f"Gran Consiglio — nuovo ordine #{order.id}",
    )
