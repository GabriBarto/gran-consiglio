"""
In-app notification history (see app/order_events.py for the writer — one
row per order state change plus "new order" at checkout) and push-device
registration (Firebase Cloud Messaging, via app/push_utils.py).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import User, db
from ..dependencies import get_current_user
from ..schemas import NotificationPublic, PushTokenRequest

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=List[NotificationPublic])
def list_my_notifications(user: User = Depends(get_current_user)) -> List[NotificationPublic]:
    return db.list_notifications(user.id)


@router.post("/notifications/{notification_id}/read", response_model=NotificationPublic)
def mark_notification_read(notification_id: str, user: User = Depends(get_current_user)) -> NotificationPublic:
    try:
        return db.mark_notification_read(user_id=user.id, notification_id=notification_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notifica non trovata.")


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(user: User = Depends(get_current_user)) -> None:
    db.mark_all_notifications_read(user.id)


# ---------------------------------------------------------------------------
# Push device registration — a device token belongs to whichever account is
# currently signed in on it, not permanently to one user (see
# Repository.register_push_token), so this lives under the authenticated
# user's own namespace rather than under /notifications.
# ---------------------------------------------------------------------------

@router.post("/users/me/push-tokens", status_code=status.HTTP_204_NO_CONTENT)
def register_push_token(payload: PushTokenRequest, user: User = Depends(get_current_user)) -> None:
    db.register_push_token(user_id=user.id, token=payload.token, platform=payload.platform.value)


@router.delete("/users/me/push-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(token: str, user: User = Depends(get_current_user)) -> None:
    """No ownership check beyond being logged in at all: unregistering a
    token that isn't yours (or doesn't exist) just no-ops — see
    Repository.unregister_push_token — there's nothing sensitive to leak
    either way, unlike an order or a shop."""
    db.unregister_push_token(token)
