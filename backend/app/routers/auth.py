"""
Authentication & account-creation endpoints:
  - registration (customer / vendor, the latter with license upload)
  - email verification (link token or OTP code)
  - login (issues JWT access + refresh tokens)
  - refresh token rotation
  - "forgot password" / "reset password"
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .. import email_utils, security, storage
from ..config import settings
from ..database import User, db, to_public_user
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterCustomerRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenPair,
    UserPublic,
    UserRole,
    VerifyEmailRequest,
)
from ..validation import is_valid_email, is_valid_phone, validate_password, validate_username

router = APIRouter(prefix="/auth", tags=["auth"])


def _uniqueness_error(exc: ValueError) -> HTTPException:
    if str(exc) == "email_taken":
        return HTTPException(status.HTTP_409_CONFLICT, "Questa email è già registrata.")
    if str(exc) == "username_taken":
        return HTTPException(status.HTTP_409_CONFLICT, "Questo nome utente è già in uso, scegline un altro.")
    return HTTPException(status.HTTP_400_BAD_REQUEST, "Richiesta non valida.")


def _start_email_verification(user: User) -> None:
    """Issues a verification link token *and* a short OTP code, and "sends"
    both via email_utils (console mock unless SMTP is configured) — either
    one can be used to complete verification."""
    token = security.create_email_verification_token(user.id)
    otp = security.generate_otp()
    db.pending_verifications[user.id] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_expire_minutes),
    }
    email_utils.send_verification_email(to=user.email, token=token, otp=otp)


def _issue_token_pair(user: User) -> TokenPair:
    access = security.create_access_token(user.id)
    refresh = security.create_refresh_token(user.id)
    refresh_payload = security.decode_token(refresh, expected_purpose="refresh")
    db.refresh_tokens[refresh_payload["jti"]] = {"user_id": user.id, "revoked": False}
    return TokenPair(access_token=access, refresh_token=refresh)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@router.post("/register/customer", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register_customer(payload: RegisterCustomerRequest) -> UserPublic:
    try:
        user = db.create_user(
            role=UserRole.CUSTOMER,
            email=payload.email,
            username=payload.username,
            password_hash=security.hash_password(payload.password),
        )
    except ValueError as exc:
        raise _uniqueness_error(exc)

    _start_email_verification(user)
    return to_public_user(user)


@router.post("/register/vendor", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_vendor(
    email: str = Form(...),
    username: str = Form(..., description="Può essere il nome del negozio"),
    password: str = Form(...),
    password_confirm: str = Form(...),
    phone: str = Form(...),
    shop_address: str = Form(...),
    license_file: UploadFile = File(..., description="Documento di licenza (PDF, JPEG o PNG)"),
) -> UserPublic:
    # multipart/form-data can't carry a nested Pydantic body the way a JSON
    # request can, so the same validation.py rules used by
    # RegisterCustomerRequest are applied by hand here.
    errors = []
    if not is_valid_email(email):
        errors.append("Email non valida.")
    username_error = validate_username(username)
    if username_error:
        errors.append(username_error)
    password_error = validate_password(password)
    if password_error:
        errors.append(password_error)
    if password != password_confirm:
        errors.append("Le password non coincidono.")
    if not is_valid_phone(phone):
        errors.append("Numero di telefono non valido.")
    if not shop_address.strip():
        errors.append("L'indirizzo del negozio è obbligatorio.")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": errors})

    try:
        user = db.create_user(
            role=UserRole.VENDOR,
            email=email,
            username=username,
            password_hash=security.hash_password(password),
        )
    except ValueError as exc:
        raise _uniqueness_error(exc)

    data = await license_file.read()
    try:
        stored = storage.save_license_file(
            user_id=user.id,
            filename=license_file.filename,
            content_type=license_file.content_type,
            data=data,
        )
    except storage.UploadRejected as exc:
        # The account itself is created; only the license upload (and thus
        # the store) failed. Surface that clearly — the client can retry
        # via POST /shops once they have a working file.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Account creato, ma il caricamento della licenza è fallito: {exc}",
        )

    # The real schema ties the license to a `store` row, not to the user
    # account (see backend/db/projectwork_en_v2.sql), so registering as a
    # vendor creates a minimal placeholder store right away — using the
    # phone/address collected here — so the license has somewhere to live.
    # lat/lng and hours are unknown at this point; the vendor fills them in
    # afterwards via PUT /shops/me.
    db.create_shop(
        vendor_id=user.id,
        name=username.strip(),
        address=shop_address.strip(),
        lat=0.0,
        lng=0.0,
        phone=phone.strip(),
        license_url=stored.url,
        opening_time="09:00",
        pickup_window_start="18:00",
        pickup_window_end="19:00",
    )

    _start_email_verification(user)
    return to_public_user(user)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest) -> MessageResponse:
    user: User | None = None

    if payload.token:
        try:
            data = security.decode_token(payload.token, expected_purpose="email_verification")
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link di verifica non valido o scaduto.")
        user = db.get_by_id(data["sub"])
    else:
        user = db.get_by_email(payload.email)
        pending = db.pending_verifications.get(user.id) if user else None
        otp_valid = (
            pending is not None
            and pending["otp"] == payload.otp
            and pending["expires_at"] >= datetime.now(timezone.utc)
        )
        if not user or not otp_valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Codice OTP non valido o scaduto.")

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Utente non trovato.")

    user.email_verified = True
    db.save(user)
    db.pending_verifications.pop(user.id, None)
    return MessageResponse(message="Email verificata con successo.")


@router.post("/verify-email/resend", response_model=MessageResponse)
def resend_verification(payload: ResendVerificationRequest) -> MessageResponse:
    user = db.get_by_email(payload.email)
    if user and not user.email_verified:
        _start_email_verification(user)
    # Always return the same generic message, whether or not the email is
    # registered/already verified, to avoid leaking account existence.
    return MessageResponse(message="Se l'indirizzo è registrato e non ancora verificato, riceverai una nuova email.")


# ---------------------------------------------------------------------------
# Login / tokens
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest) -> TokenPair:
    user = db.get_by_email(payload.email)
    if not user or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o password non corretti.")

    return _issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh_token(payload: RefreshRequest) -> TokenPair:
    try:
        data = security.decode_token(payload.refresh_token, expected_purpose="refresh")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token non valido o scaduto.")

    record = db.refresh_tokens.get(data["jti"])
    if not record or record["revoked"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token non valido o già utilizzato.")

    user = db.get_by_id(data["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utente non trovato.")

    # Rotate: the old refresh token is single-use — invalidate it and hand
    # back a brand new access/refresh pair.
    record["revoked"] = True
    return _issue_token_pair(user)


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------

@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    user = db.get_by_email(payload.email)
    if user:
        token = security.create_password_reset_token(user.id)
        payload_claims = security.decode_token(token, expected_purpose="password_reset")
        db.pending_resets[user.id] = {"jti": payload_claims["jti"]}
        email_utils.send_password_reset_email(to=user.email, token=token)

    # Same response regardless of whether the email exists, to avoid
    # leaking which addresses are registered.
    return MessageResponse(message="Se l'indirizzo è registrato, riceverai un'email per reimpostare la password.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    try:
        data = security.decode_token(payload.token, expected_purpose="password_reset")
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token non valido o scaduto.")

    user = db.get_by_id(data["sub"])
    pending = db.pending_resets.get(user.id) if user else None
    if not user or not pending or pending["jti"] != data["jti"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token non valido o già utilizzato.")

    user.password_hash = security.hash_password(payload.new_password)
    db.save(user)
    db.pending_resets.pop(user.id, None)
    return MessageResponse(message="Password aggiornata con successo.")
