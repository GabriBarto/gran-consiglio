"""
Pytest session setup: points the app at a dedicated `toogood_test` MySQL
database (never the dev/seed `toogood` one) and (re)loads it fresh from
backend/db/projectwork_en_v2.sql before anything else runs, so the test
suite starts from the exact same known seed data every time, regardless of
what earlier runs (or manual poking) left behind.

This module-level code runs before pytest imports any test file in this
directory — critically, before `app.config.settings` (which reads
DATABASE_URL at import time) is ever imported.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

TEST_DB_NAME = "toogood_test"
os.environ["DATABASE_URL"] = f"mysql+pymysql://root:@127.0.0.1:3306/{TEST_DB_NAME}"

_MYSQL_BIN = os.environ.get("MYSQL_BIN", r"C:\xampp\mysql\bin\mysql.exe")
_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "projectwork_en_v2.sql"


def _run_sql(sql: str) -> None:
    subprocess.run([_MYSQL_BIN, "-u", "root"], input=sql, text=True, check=True, capture_output=True, encoding="utf-8")


def _reset_test_database() -> None:
    _run_sql(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`;")
    sql_text = _SCHEMA_FILE.read_text(encoding="utf-8")
    # The file creates/targets the `toogood` dev database by name; point
    # this run at `toogood_test` instead without needing a second copy.
    sql_text = sql_text.replace("`toogood`", f"`{TEST_DB_NAME}`")
    _run_sql(sql_text)


_reset_test_database()
