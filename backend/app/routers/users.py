"""
Authenticated account endpoints: current profile, license document
management, and the customer -> vendor "upgrade account" flow.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .. import storage
from ..database import License, User, db, to_public_user
from ..dependencies import get_current_user, require_vendor
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
    vendor registration time."""
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
    user.phone = phone.strip()
    user.shop_address = shop_address.strip()
    # A real backend would leave this pending until a human/automated check
    # reviews the document — same convention as registration.
    user.license = License(file_name=stored.file_name, content_type=stored.content_type, storage_url=stored.url)
    db.save(user)
    return to_public_user(user)


@router.put("/me/license", response_model=UserPublic)
async def replace_license(
    license_file: UploadFile = File(..., description="Documento di licenza (PDF, JPEG o PNG)"),
    user: User = Depends(require_vendor),
) -> UserPublic:
    """Lets a vendor (re)upload their license document, e.g. after a
    rejection or to replace an expired one. Re-uploading resets the review
    status to pending."""
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

    user.license = License(file_name=stored.file_name, content_type=stored.content_type, storage_url=stored.url)
    db.save(user)
    return to_public_user(user)
