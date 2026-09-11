"""
Password hashing + JWT helpers.

Passwords: passlib's CryptContext with argon2 as the default/preferred
scheme (bcrypt is kept as a second, verifiable scheme — e.g. useful if
hashes were ever imported from a system that used bcrypt). Swap the
`schemes` order to prefer bcrypt instead if that's the team's call; either
way, plaintext passwords are never stored or logged.

Tokens: python-jose (JWT). The same encode/decode helpers back four
different token "purposes", distinguished by a `purpose` claim:
  - access / refresh tokens for authentication (short / long lived)
  - single-use tokens for email verification and password reset links
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        # Malformed/unknown hash format — never crash the login endpoint.
        return False


def _create_token(*, subject: str, purpose: str, expires_delta: timedelta, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "purpose": purpose,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_purpose: Optional[str] = None) -> dict:
    """Decodes and validates a JWT (signature + expiry). Raises ValueError
    (never a jose-specific exception) on any invalid/expired/wrong-purpose
    token, so callers only need to catch one thing."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc
    if expected_purpose and payload.get("purpose") != expected_purpose:
        raise ValueError("invalid_token")
    return payload


def create_access_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        purpose="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        purpose="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def create_email_verification_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        purpose="email_verification",
        expires_delta=timedelta(minutes=settings.email_verification_expire_minutes),
    )


def create_password_reset_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        purpose="password_reset",
        expires_delta=timedelta(minutes=settings.password_reset_expire_minutes),
    )


def generate_otp(length: int = 6) -> str:
    """Cryptographically-random numeric OTP, e.g. for email verification
    codes typed in-app instead of clicking the link."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))
