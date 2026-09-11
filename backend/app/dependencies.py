"""
FastAPI dependencies for authenticated routes: resolve the current user from
a Bearer access token, and gate vendor-only endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import security
from .database import User, db
from .schemas import UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticazione richiesta.")
    try:
        payload = security.decode_token(credentials.credentials, expected_purpose="access")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token non valido o scaduto.")

    user = db.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utente non trovato.")
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Optional[User]:
    """Like get_current_user, but never raises: returns None if there is no
    token, or if it's invalid/expired. For endpoints that are public but
    behave differently for a logged-in owner/admin (e.g. GET /shops/{id}
    showing an unapproved shop only to its own vendor)."""
    if credentials is None:
        return None
    try:
        payload = security.decode_token(credentials.credentials, expected_purpose="access")
    except ValueError:
        return None
    return db.get_by_id(payload["sub"])


def require_vendor(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.VENDOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Endpoint disponibile solo per i venditori.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Endpoint disponibile solo per gli amministratori.")
    return user
