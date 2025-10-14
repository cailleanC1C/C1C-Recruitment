"""Thin wrappers over gspread to centralise authentication."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception as exc:  # pragma: no cover - optional dependency at import time
    gspread = None  # type: ignore
    Credentials = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _service_account_info() -> dict[str, Any]:
    raw = (
        os.getenv("GSPREAD_CREDENTIALS")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or ""
    )
    if not raw:
        raise RuntimeError("GSPREAD_CREDENTIALS/GOOGLE_SERVICE_ACCOUNT_JSON not set")
    return json.loads(raw)


@lru_cache(maxsize=1)
def get_service_account_client():
    if gspread is None or Credentials is None:
        raise RuntimeError("gspread is not installed") from _IMPORT_ERROR
    info = _service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def open_by_key(sheet_id: str | None = None):
    if sheet_id is None:
        sheet_id = os.getenv("GOOGLE_SHEET_ID") or os.getenv("GSHEET_ID") or ""
    sheet_id = sheet_id.strip()
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID/GSHEET_ID not set")
    client = get_service_account_client()
    return client.open_by_key(sheet_id)
