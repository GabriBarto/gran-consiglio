"""
Review endpoints: a customer leaving a review on one of their own
picked-up orders, reading a shop's reviews (public), and reporting a
review for moderation (see routers/admin.py for the admin-only
list-reported / remove / restore side).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..database import User, db
from ..dependencies import get_current_user, get_optional_current_user
from ..schemas import (
    LicenseStatus,
    MessageResponse,
    ReviewListResponse,
    ReviewPublic,
    ReviewReportRequest,
    ReviewRequest,
    UserRole,
)

router = APIRouter(tags=["reviews"])


# ---------------------------------------------------------------------------
# Create (tied to one of the caller's own picked-up orders)
# ---------------------------------------------------------------------------

@router.post("/orders/{order_id}/reviews", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_review(order_id: str, payload: ReviewRequest, user: User = Depends(get_current_user)) -> ReviewPublic:
    owner = db.get_order_owner_ids(order_id)
    if not owner or owner[0] != user.id:
        # 404, not 403: same anti-enumeration convention as
        # routers/orders.py (don't confirm a stranger's order exists).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")
    try:
        return db.create_review(order_id=order_id, user_id=user.id, rating=payload.rating, text=payload.text)
    except ValueError as exc:
        if str(exc) == "not_picked_up":
            raise HTTPException(status.HTTP_409_CONFLICT, "Puoi recensire solo un ordine già ritirato.")
        if str(exc) == "already_reviewed":
            raise HTTPException(status.HTTP_409_CONFLICT, "Hai già recensito questo ordine.")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordine non trovato.")


# ---------------------------------------------------------------------------
# Read (public, same visibility rule as the shop itself)
# ---------------------------------------------------------------------------

@router.get("/shops/{shop_id}/reviews", response_model=ReviewListResponse)
def list_shop_reviews(
    shop_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(get_optional_current_user),
) -> ReviewListResponse:
    shop = db.get_shop(shop_id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")

    is_owner = user is not None and user.id == shop.vendor_id
    is_admin = user is not None and user.role == UserRole.ADMIN
    if shop.license_status != LicenseStatus.APPROVED and not (is_owner or is_admin):
        # Same privacy rule as GET /shops/{shop_id}: don't reveal a
        # not-yet-approved shop's reviews to the public either.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")

    items, total, average_rating = db.list_reviews_for_shop(shop_id, limit=limit, offset=offset)
    return ReviewListResponse(total=total, limit=limit, offset=offset, average_rating=average_rating, items=items)


@router.get("/reviews/{review_id}", response_model=ReviewPublic)
def get_review(review_id: str) -> ReviewPublic:
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")
    return review


# ---------------------------------------------------------------------------
# Update / delete (author only)
# ---------------------------------------------------------------------------

@router.put("/reviews/{review_id}", response_model=ReviewPublic)
def update_review(review_id: str, payload: ReviewRequest, user: User = Depends(get_current_user)) -> ReviewPublic:
    owner_id = db.get_review_owner_id(review_id)
    if not owner_id or owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")
    try:
        return db.update_review(review_id, rating=payload.rating, text=payload.text)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: str, user: User = Depends(get_current_user)) -> None:
    """Soft delete (see Repository.set_review_removed) — the same
    mechanism the admin moderation endpoint uses, so the review stays
    available for audit rather than disappearing outright."""
    owner_id = db.get_review_owner_id(review_id)
    if not owner_id or owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")
    try:
        db.set_review_removed(review_id, removed=True)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")


# ---------------------------------------------------------------------------
# Report (any authenticated user)
# ---------------------------------------------------------------------------

@router.post("/reviews/{review_id}/report", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def report_review(
    review_id: str, payload: ReviewReportRequest, user: User = Depends(get_current_user)
) -> MessageResponse:
    """A report never hides the review on its own — see
    PATCH /admin/reviews/{id} in routers/admin.py for the actual removal."""
    try:
        db.report_review(review_id, user_id=user.id, reason=payload.reason)
    except ValueError as exc:
        if str(exc) == "already_reported":
            raise HTTPException(status.HTTP_409_CONFLICT, "Hai già segnalato questa recensione.")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recensione non trovata.")
    return MessageResponse(message="Segnalazione registrata.")
