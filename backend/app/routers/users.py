"""
Authenticated account endpoints: current profile, and the customer ->
vendor "upgrade account" flow. License document management now lives on
the shop (PUT /shops/me/license, see routers/shops.py) since the real
schema ties licenseUrl/verificationStatus to `store`, not to `user`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .. import storage
from ..database import User, db, to_public_user
from ..dependencies import get_current_user
from ..schemas import UserPublic, UserRole
from ..validation import is_valid_phone

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def read_me(user: User = Depends(get_current_user)) -> UserPublic:
    return to_public_user(user)


@router.post("/me/upgrade-to-vendor", response_model=UserPublic)
async def upgrade_to_vendor(
    phone: str = Form(...),
    shop_address: str = Form(...),
    license_file: UploadFile = File(..., description="Documento di licenza (PDF, JPEG o PNG)"),
    user: User = Depends(get_current_user),
) -> UserPublic:
    """Lets an existing customer become a vendor, providing the same
    extra details (phone, shop address, license document) collected at
    vendor registration time — and, like registration, creates a minimal
    placeholder store (see routers/auth.py::register_vendor) since the
    license lives on `store`, not on the user account."""
    if user.role == UserRole.VENDOR:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "L'account è già un account venditore.")
    if not is_valid_phone(phone):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numero di telefono non valido.")
    if not shop_address.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'indirizzo del negozio è obbligatorio.")

    data = await license_file.read()
    try:
        stored = storage.save_license_file(
            user_id=user.id,
            filename=license_file.filename,
            content_type=license_file.content_type,
            data=data,
        )
    except storage.UploadRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    user.role = UserRole.VENDOR
    db.save(user)

    # A real backend would leave this pending until a human/automated check
    # reviews the document — same convention as registration.
    db.create_shop(
        vendor_id=user.id,
        name=user.username,
        address=shop_address.strip(),
        lat=0.0,
        lng=0.0,
        phone=phone.strip(),
        license_url=stored.url,
        opening_time="09:00",
        pickup_window_start="18:00",
        pickup_window_end="19:00",
    )
    return to_public_user(user)
