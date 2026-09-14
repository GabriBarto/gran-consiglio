"""
Shared validation rules for account fields.

Kept in sync on purpose with src/validation.js on the Expo frontend, so the
client-side checks and the (authoritative) server-side checks agree on what
counts as a valid email/password/username/phone.
"""
from __future__ import annotations

import re
from typing import Optional

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Mirrors PHONE_RE in validation.js: leading + or digit, then 8-19 more
# digits/spaces/hyphens.
PHONE_RE = re.compile(r"^[+\d][\d\s-]{7,18}$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(str(email or "").strip()))


def validate_password(password: str) -> Optional[str]:
    """Returns an error message, or None if the password is acceptable."""
    if not password or len(password) < 8:
        return "La password deve contenere almeno 8 caratteri."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "La password deve contenere almeno una lettera e un numero."
    return None


def _is_allowed_username_char(ch: str) -> bool:
    # Equivalent to the JS character class [\p{L}0-9 _-] (unicode letters,
    # digits, space, underscore, hyphen).
    return ch.isalpha() or ch.isdigit() or ch in " _-"


def validate_username(username: str) -> Optional[str]:
    trimmed = str(username or "").strip()
    if not (3 <= len(trimmed) <= 30) or not all(_is_allowed_username_char(c) for c in trimmed):
        return "Il nome utente deve avere 3-30 caratteri (lettere, numeri, spazi, - o _)."
    return None


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(str(phone or "").strip()))


def normalize_identifier(value: str) -> str:
    """Usernames/emails are compared normalized so "Vivaio Rossi" and
    "vivaio  rossi" are treated as the same identity, same as
    normalizeIdentifier() in validation.js."""
    return " ".join(str(value or "").strip().lower().split())
