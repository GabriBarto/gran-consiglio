"""
Central app configuration, read from environment variables / a local .env
file (see .env.example). Users and shops are now persisted in a real MySQL
(MariaDB-compatible) database — see backend/db/projectwork_en_v2.sql for the
schema and app/db/ for the SQLAlchemy layer. Mail/storage remain
fake/mock implementations for now — see email_utils.py and storage.py.
"""
from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gran Consiglio / TooGood API"

    # MySQL/MariaDB connection. Default matches a stock local XAMPP install
    # (root, no password, default port). Point this at a different server
    # via the DATABASE_URL env var / .env — nothing else needs to change,
    # see app/db/engine.py.
    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/toogood"

    # WARNING: this default is for local development only. Always set a
    # real SECRET_KEY via environment variable (or .env, never committed)
    # in any shared or deployed environment.
    secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    email_verification_expire_minutes: int = 60 * 24
    password_reset_expire_minutes: int = 30

    # SMTP is optional: leave SMTP_HOST unset to use the console "mock"
    # email backend (see email_utils.py), which logs the email instead of
    # sending it — handy for local dev / grading without real credentials.
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "no-reply@toogood.example"
    smtp_use_tls: bool = True

    # Local-disk file storage for vendor license uploads (see storage.py).
    # Real files, really served by this same API (mounted in main.py) —
    # only self-hosted rather than a cloud bucket. Only the resulting
    # URL/metadata is ever stored in the DB, never the file bytes.
    #
    # A relative value is resolved against the backend/ package directory
    # (see storage.py), NOT against the process's current working
    # directory — uvicorn can be launched from the repo root or from
    # inside backend/, and this keeps the upload path identical either
    # way instead of silently nesting into backend/backend/... Pass an
    # absolute path here (env var) to point at a different location.
    license_storage_dir: str = "uploads/licenses"
    max_license_size_mb: int = 10

    # Where THIS API is publicly reachable from clients — used to build
    # real, working URLs for files it serves itself (uploaded licenses).
    # Keep in sync with EXPO_PUBLIC_API_BASE_URL in the frontend's own
    # .env (project root): same backend, same address. Swap for your real
    # domain (https://api.yourapp.com) once deployed.
    public_base_url: str = "http://127.0.0.1:8000"

    # Used to build the links embedded in verification / reset emails.
    frontend_base_url: str = "http://localhost:8081"

    # Push notifications (Firebase Cloud Messaging, via firebase-admin —
    # see app/push_utils.py). Optional, same pattern as SMTP above: leave
    # unset to use the console "mock" push backend (logs instead of
    # sending), handy for local dev without a real Firebase project. Set
    # to the path of a service account JSON downloaded from the Firebase
    # console (Project settings -> Service accounts -> Generate new
    # private key) to send real pushes.
    firebase_credentials_file: Optional[str] = None


settings = Settings()
