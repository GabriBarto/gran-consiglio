"""
File storage layer for vendor license uploads.

License documents must never live in the relational database — only a
reference (URL + metadata) to the stored object does. Files are written to
disk under LICENSE_STORAGE_DIR and are NOT publicly served: the only way
to download one is GET /shops/{id}/license with a short-lived token that
only an admin or the shop's own vendor can obtain (see routers/shops.py).
The URL stored in the DB just identifies the file (resolve_license_path()). Swap save_license_file()'s body for e.g. a
boto3 upload_fileobj() (S3) or google-cloud-storage Blob.upload_from_file()
(GCS) call when a real bucket is available — callers (routers/*.py) only
depend on the StoredFile shape returned here, so nothing else would change.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import settings

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}

# backend/ (this file's grandparent: backend/app/storage.py -> backend/).
_BACKEND_DIR = Path(__file__).resolve().parent.parent

_configured_dir = Path(settings.license_storage_dir)
# Anchor a relative path to backend/ rather than to the process's cwd, so
# the upload location is the same whether uvicorn is launched from the
# repo root or from inside backend/ (see the comment on license_storage_dir
# in config.py — this is what fixes the backend/backend/uploads nesting).
UPLOAD_DIR = _configured_dir if _configured_dir.is_absolute() else _BACKEND_DIR / _configured_dir
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# URL prefix of the stored license_url values. Nothing is mounted here any
# more (files are private), it only identifies the file — see
# resolve_license_path().
UPLOAD_URL_PATH = "/uploads/licenses"


class UploadRejected(Exception):
    """Raised for any problem with the uploaded file that the caller should
    turn into a 4xx response (too big, empty, wrong type, ...)."""


@dataclass
class StoredFile:
    file_name: str
    content_type: Optional[str]
    url: str


def save_license_file(*, user_id: str, filename: Optional[str], content_type: Optional[str], data: bytes) -> StoredFile:
    if not data:
        raise UploadRejected("Il file caricato è vuoto.")

    max_bytes = settings.max_license_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadRejected(f"Il file supera la dimensione massima di {settings.max_license_size_mb} MB.")

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise UploadRejected("Formato non supportato. Carica un PDF, JPEG o PNG.")

    ext = Path(filename or "").suffix
    stored_name = f"{user_id}_{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(data)

    # Not directly downloadable (see module docstring). With a real bucket
    # this would be the object's key/URL instead, e.g.:
    #   s3_client.upload_fileobj(io.BytesIO(data), bucket, key)
    #   url = f"https://{bucket}.s3.amazonaws.com/{key}"
    url = f"{settings.public_base_url.rstrip('/')}{UPLOAD_URL_PATH}/{stored_name}"
    return StoredFile(file_name=filename or stored_name, content_type=content_type, url=url)


def resolve_license_path(license_url: Optional[str]) -> Optional[Path]:
    """Maps a stored license_url back to the file on disk, or None if it
    doesn't point to a file we have (e.g. seed data with a placeholder URL).
    Only the last path segment is used and it must stay inside UPLOAD_DIR,
    so a crafted URL can never reach other files."""
    if not license_url:
        return None
    name = license_url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if not name or name in (".", "..") or "\\" in name:
        return None
    path = (UPLOAD_DIR / name).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        return None
    return path
