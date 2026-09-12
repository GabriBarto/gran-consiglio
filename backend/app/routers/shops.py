"""
Shop (vendor storefront) endpoints: CRUD for the vendor's own shop, license
document (re)upload, and a public search by address/lat/lng/radius.
Admin-only license-status moderation lives in routers/admin.py, not here —
a vendor's own create/update requests structurally cannot include
license_status at all (see schemas.ShopRequest).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from .. import geo, storage
from ..database import Shop, User, db, to_public_shop
from ..dependencies import get_optional_current_user, require_vendor
from ..schemas import LicenseStatus, ShopPublic, ShopRequest, ShopSearchResponse, UserRole
from ..validation import normalize_identifier

router = APIRouter(prefix="/shops", tags=["shops"])


def _my_shop_or_404(vendor: User) -> Shop:
    shop = db.get_shop_by_vendor(vendor.id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Non hai ancora registrato un negozio.")
    return shop


# ---------------------------------------------------------------------------
# CRUD on the caller's own shop (vendor only)
# ---------------------------------------------------------------------------

@router.post("", response_model=ShopPublic, status_code=status.HTTP_201_CREATED)
async def create_shop(
    name: str = Form(...),
    address: str = Form(...),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    phone: str = Form(...),
    opening_time: str = Form(...),
    pickup_window_start: str = Form(...),
    pickup_window_end: str = Form(...),
    license_file: UploadFile = File(..., description="Documento di licenza (PDF, JPEG o PNG)"),
    vendor: User = Depends(require_vendor),
) -> ShopPublic:
    """Creates the vendor's shop from scratch (multipart, license file
    included) — most vendors already have one auto-created at registration
    / upgrade-to-vendor time (see routers/auth.py, routers/users.py); this
    is for the case where that one was deleted, or wasn't created (e.g. an
    account provisioned directly in the DB)."""
    # Reuse the same field-level rules as ShopRequest (JSON body) by hand,
    # since multipart can't carry a nested Pydantic model here.
    try:
        payload = ShopRequest(
            name=name, address=address, lat=lat, lng=lng, phone=phone,
            opening_time=opening_time, pickup_window_start=pickup_window_start,
            pickup_window_end=pickup_window_end,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    if db.get_shop_by_vendor(vendor.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Hai già un negozio registrato.")

    data = await license_file.read()
    try:
        stored = storage.save_license_file(
            user_id=vendor.id, filename=license_file.filename, content_type=license_file.content_type, data=data,
        )
    except storage.UploadRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    shop = db.create_shop(
        vendor_id=vendor.id,
        name=payload.name,
        address=payload.address,
        lat=payload.lat,
        lng=payload.lng,
        phone=payload.phone,
        license_url=stored.url,
        opening_time=payload.opening_time,
        pickup_window_start=payload.pickup_window_start,
        pickup_window_end=payload.pickup_window_end,
    )
    return to_public_shop(shop)


@router.get("/me", response_model=ShopPublic)
def read_my_shop(vendor: User = Depends(require_vendor)) -> ShopPublic:
    return to_public_shop(_my_shop_or_404(vendor))


@router.put("/me", response_model=ShopPublic)
def update_my_shop(payload: ShopRequest, vendor: User = Depends(require_vendor)) -> ShopPublic:
    """Updates the shop's own details. License (file + review status) is
    deliberately not editable here — see PUT /shops/me/license and
    PATCH /admin/shops/{id}/license-status."""
    shop = _my_shop_or_404(vendor)
    shop.name = payload.name
    shop.address = payload.address
    shop.lat = payload.lat
    shop.lng = payload.lng
    shop.phone = payload.phone
    shop.opening_time = payload.opening_time
    shop.pickup_window_start = payload.pickup_window_start
    shop.pickup_window_end = payload.pickup_window_end
    db.save_shop(shop)
    return to_public_shop(shop)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_shop(vendor: User = Depends(require_vendor)) -> None:
    shop = _my_shop_or_404(vendor)
    db.delete_shop(shop.id)


@router.put("/me/license", response_model=ShopPublic)
async def replace_license(
    license_file: UploadFile = File(..., description="Documento di licenza (PDF, JPEG o PNG)"),
    vendor: User = Depends(require_vendor),
) -> ShopPublic:
    """Lets a vendor (re)upload their license document, e.g. after a
    rejection or to replace an expired one. Re-uploading resets the review
    status to pending — only an admin can approve/reject it again."""
    shop = _my_shop_or_404(vendor)
    data = await license_file.read()
    try:
        stored = storage.save_license_file(
            user_id=vendor.id, filename=license_file.filename, content_type=license_file.content_type, data=data,
        )
    except storage.UploadRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    shop.license_url = stored.url
    shop.license_status = LicenseStatus.PENDING_REVIEW
    db.save_shop(shop)
    return to_public_shop(shop)


# ---------------------------------------------------------------------------
# Public read / search
# ---------------------------------------------------------------------------

@router.get("", response_model=ShopSearchResponse)
def search_shops(
    city: Optional[str] = Query(
        None, description="Cerca nell'indirizzo (case-insensitive, corrispondenza parziale) — non c'è un campo città separato nello schema."
    ),
    lat: Optional[float] = Query(None, ge=-90, le=90, description="Latitudine del punto di ricerca"),
    lng: Optional[float] = Query(None, ge=-180, le=180, description="Longitudine del punto di ricerca"),
    radius_km: Optional[float] = Query(None, gt=0, description="Richiede lat e lng"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ShopSearchResponse:
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "lat e lng vanno forniti insieme.")
    if radius_km is not None and lat is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "radius_km richiede lat e lng.")

    # Only ever surface admin-approved shops to public search — a shop
    # that's still pending_review or was rejected isn't a real storefront
    # yet from a customer's point of view.
    shops = [s for s in db.list_shops() if s.license_status == LicenseStatus.APPROVED]

    if city:
        target = normalize_identifier(city)
        shops = [s for s in shops if target in normalize_identifier(s.address)]

    if lat is not None and lng is not None:
        scored = [(s, geo.haversine_km(lat, lng, s.lat, s.lng)) for s in shops]
        if radius_km is not None:
            scored = [pair for pair in scored if pair[1] <= radius_km]
        scored.sort(key=lambda pair: pair[1])
    else:
        scored = [(s, None) for s in sorted(shops, key=lambda s: s.name.lower())]

    total = len(scored)
    page = scored[offset : offset + limit]
    return ShopSearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_public_shop(s, distance_km=d) for s, d in page],
    )


@router.get("/{shop_id}", response_model=ShopPublic)
def read_shop(shop_id: str, user: Optional[User] = Depends(get_optional_current_user)) -> ShopPublic:
    shop = db.get_shop(shop_id)
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")

    is_owner = user is not None and user.id == shop.vendor_id
    is_admin = user is not None and user.role == UserRole.ADMIN
    if shop.license_status != LicenseStatus.APPROVED and not (is_owner or is_admin):
        # Hide the existence of unapproved shops from everyone else,
        # same as a plain 404 (not a 403) so it can't be used to probe
        # which shop ids are pending/rejected.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Negozio non trovato.")

    return to_public_shop(shop)
