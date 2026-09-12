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

    # Fake object storage standing in for S3 / Google Cloud Storage until a
    # real bucket is wired up (see storage.py). Files are written to disk
    # here; only the resulting URL/metadata is ever stored on the "DB".
    #
    # A relative value is resolved against the backend/ package directory
    # (see storage.py), NOT against the process's current working
    # directory — uvicorn can be launched from the repo root or from
    # inside backend/, and this keeps the upload path identical either
    # way instead of silently nesting into backend/backend/... Pass an
    # absolute path here (env var) to point at a different location.
    fake_storage_dir: str = "uploads/licenses"
    fake_storage_base_url: str = "https://fake-bucket.local/licenses"
    max_license_size_mb: int = 10

    # Used to build the links embedded in verification / reset emails.
    frontend_base_url: str = "http://localhost:8081"


settings = Settings()
