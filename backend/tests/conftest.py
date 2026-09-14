"""
Pytest session setup: points the app at a dedicated `toogood_test` MySQL
database (never the dev/seed `toogood` one) and (re)loads it fresh from
backend/db/projectwork_en_v2.sql before anything else runs, so the test
suite starts from the exact same known seed data every time, regardless of
what earlier runs (or manual poking) left behind.

Cross-platform (Windows/XAMPP, macOS/Homebrew or MAMP, Linux, ...): every
connection detail is a `TEST_DB_*` environment variable with a
Windows/XAMPP-compatible default (root, no password, 127.0.0.1:3306), and
the mysql client binary is auto-detected (PATH, then a couple of common
install locations) unless MYSQL_BIN overrides it. Nothing here needs
editing per-machine — set env vars instead (e.g. in backend/.env, though
note this file itself doesn't load .env; export them in your shell, or see
README.md).

This module-level code runs before pytest imports any test file in this
directory — critically, before `app.config.settings` (which reads
DATABASE_URL at import time) is ever imported.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "toogood_test")
_DB_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")
_DB_PORT = os.environ.get("TEST_DB_PORT", "3306")
_DB_USER = os.environ.get("TEST_DB_USER", "root")
_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "")

os.environ["DATABASE_URL"] = (
    f"mysql+pymysql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:{_DB_PORT}/{TEST_DB_NAME}"
)

# Common mysql client locations, tried in order, after MYSQL_BIN/PATH.
_FALLBACK_MYSQL_BINS = [
    r"C:\xampp\mysql\bin\mysql.exe",  # Windows, XAMPP
    "/Applications/MAMP/Library/bin/mysql80/bin/mysql",  # macOS, MAMP
    "/Applications/XAMPP/xamppfiles/bin/mysql",  # macOS, XAMPP
]


def _find_mysql_bin() -> str:
    candidates = [os.environ.get("MYSQL_BIN"), shutil.which("mysql"), *_FALLBACK_MYSQL_BINS]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return candidate
    raise RuntimeError(
        "Could not find a `mysql` client binary (checked MYSQL_BIN, PATH, and common "
        "XAMPP/MAMP locations). Set the MYSQL_BIN environment variable to its full path — "
        "see backend/README.md."
    )


_MYSQL_BIN = _find_mysql_bin()
_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "projectwork_en_v2.sql"


def _mysql_args() -> list[str]:
    args = [_MYSQL_BIN, "-h", _DB_HOST, "-P", _DB_PORT, "-u", _DB_USER]
    if _DB_PASSWORD:
        args.append(f"-p{_DB_PASSWORD}")
    return args


def _run_sql(sql: str) -> None:
    subprocess.run(_mysql_args(), input=sql, text=True, check=True, capture_output=True, encoding="utf-8")


def _reset_test_database() -> None:
    _run_sql(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`;")
    sql_text = _SCHEMA_FILE.read_text(encoding="utf-8")
    # The file creates/targets the `toogood` dev database by name; point
    # this run at `toogood_test` instead without needing a second copy.
    sql_text = sql_text.replace("`toogood`", f"`{TEST_DB_NAME}`")
    _run_sql(sql_text)


_reset_test_database()
