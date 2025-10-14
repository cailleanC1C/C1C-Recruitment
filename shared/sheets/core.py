"""Thin wrappers over gspread to centralise authentication and caching."""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any, Callable, Dict, Tuple, TypeVar

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

_WorksheetT = TypeVar("_WorksheetT")
_WorkbookCache: Dict[str, Any] = {}
_WorksheetCache: Dict[Tuple[str, str], Any] = {}

_DEFAULT_ATTEMPTS = int(os.getenv("GSHEETS_RETRY_ATTEMPTS", "5"))
_DEFAULT_BACKOFF_BASE = float(os.getenv("GSHEETS_RETRY_BASE", "0.5"))
_DEFAULT_BACKOFF_FACTOR = float(os.getenv("GSHEETS_RETRY_FACTOR", "2.0"))


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


def _retry_with_backoff(
    func: Callable[..., _WorksheetT],
    *args: Any,
    attempts: int | None = None,
    base_delay: float | None = None,
    factor: float | None = None,
    **kwargs: Any,
) -> _WorksheetT:
    """Retry ``func`` using exponential backoff on failure."""

    tries = attempts or _DEFAULT_ATTEMPTS
    delay = base_delay if base_delay is not None else _DEFAULT_BACKOFF_BASE
    multiplier = factor if factor is not None else _DEFAULT_BACKOFF_FACTOR

    if tries <= 0:
        raise ValueError("attempts must be positive")

    last_exc: Exception | None = None
    for attempt in range(tries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - network/Sheets failures
            last_exc = exc
            if attempt >= tries - 1:
                raise
            time.sleep(max(0.0, delay))
            delay *= multiplier if multiplier > 1 else 1
    if last_exc is not None:  # pragma: no cover - defensive
        raise last_exc
    raise RuntimeError("_retry_with_backoff exhausted without executing")


def _resolve_sheet_id(sheet_id: str | None) -> str:
    if sheet_id is None:
        sheet_id = os.getenv("GOOGLE_SHEET_ID") or os.getenv("GSHEET_ID") or ""
    sheet_id = sheet_id.strip()
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID/GSHEET_ID not set")
    return sheet_id


def open_by_key(sheet_id: str | None = None):
    resolved = _resolve_sheet_id(sheet_id)
    if resolved in _WorkbookCache:
        return _WorkbookCache[resolved]
    client = get_service_account_client()
    workbook = _retry_with_backoff(client.open_by_key, resolved)
    _WorkbookCache[resolved] = workbook
    return workbook


def get_worksheet(sheet_id: str, name: str):
    """Return a cached ``gspread.Worksheet`` for ``sheet_id`` + ``name``."""

    key = (sheet_id, name)
    if key in _WorksheetCache:
        return _WorksheetCache[key]
    workbook = open_by_key(sheet_id)
    worksheet = _retry_with_backoff(workbook.worksheet, name)
    _WorksheetCache[key] = worksheet
    return worksheet


def fetch_records(sheet_id: str, worksheet: str):
    ws = get_worksheet(sheet_id, worksheet)
    return _retry_with_backoff(ws.get_all_records)


def fetch_values(sheet_id: str, worksheet: str):
    ws = get_worksheet(sheet_id, worksheet)
    return _retry_with_backoff(ws.get_all_values)


def call_with_backoff(func: Callable[..., _WorksheetT], *args: Any, **kwargs: Any) -> _WorksheetT:
    """Expose the retry helper for modules performing write operations."""

    return _retry_with_backoff(func, *args, **kwargs)
