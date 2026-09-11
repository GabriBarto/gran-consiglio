"""
Fake object-storage layer standing in for S3 / Google Cloud Storage.

License documents must never live in the relational database — only a
reference (URL + metadata) to the stored object does. Until a real bucket is
available, files are written to disk under FAKE_STORAGE_DIR and served
through a fake URL. Replace save_license_file()'s body with e.g. a boto3
upload_fileobj() (S3) or google-cloud-storage Blob.upload_from_file() (GCS)
call when a real bucket exists — callers (routers/*.py) only depend on the
StoredFile shape returned here, so nothing else needs to change.
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

_configured_dir = Path(settings.fake_storage_dir)
# Anchor a relative path to backend/ rather than to the process's cwd, so
# the upload location is the same whether uvicorn is launched from the
# repo root or from inside backend/ (see the comment on fake_storage_dir
# in config.py — this is what fixes the backend/backend/uploads nesting).
UPLOAD_DIR = _configured_dir if _configured_dir.is_absolute() else _BACKEND_DIR / _configured_dir
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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

    # In production this would be whatever URL the SDK hands back, e.g.:
    #   s3_client.upload_fileobj(io.BytesIO(data), bucket, key)
    #   url = f"https://{bucket}.s3.amazonaws.com/{key}"
    fake_url = f"{settings.fake_storage_base_url.rstrip('/')}/{stored_name}"
    return StoredFile(file_name=filename or stored_name, content_type=content_type, url=fake_url)
