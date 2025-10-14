"""Google Sheets adapter core shared by recruitment/onboarding modules."""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple, TypeVar

import gspread
from gspread import Worksheet
from gspread.exceptions import APIError
from gspread.utils import rowcol_to_a1

try:  # pragma: no cover - requests is an optional runtime dependency of gspread
    from requests import exceptions as requests_exceptions
except Exception:  # pragma: no cover
    requests_exceptions = None


log = logging.getLogger("c1c.sheets.core")

GSpreadClient = gspread.Client


@dataclass
class WorksheetCacheEntry:
    worksheet: Worksheet
    expires_at: float


_CLIENT_LOCK = threading.Lock()
_CLIENT: Optional[GSpreadClient] = None
_WORKSHEET_CACHE: Dict[Tuple[str, str], WorksheetCacheEntry] = {}

_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}

T = TypeVar("T")


def clear_cached_client() -> None:
    """Drop the cached gspread client (mainly for tests)."""

    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = None


def clear_cached_worksheets(spreadsheet_id: Optional[str] = None) -> None:
    """Clear the worksheet cache.

    Args:
        spreadsheet_id: If provided only entries for this spreadsheet are removed.
    """

    if not _WORKSHEET_CACHE:
        return
    if spreadsheet_id is None:
        _WORKSHEET_CACHE.clear()
        return
    keys = [key for key in _WORKSHEET_CACHE if key[0] == spreadsheet_id]
    for key in keys:
        _WORKSHEET_CACHE.pop(key, None)


def _load_credentials() -> Mapping[str, Any]:
    raw = os.getenv("GSPREAD_CREDENTIALS")
    if not raw:
        raise RuntimeError("GSPREAD_CREDENTIALS environment variable is required")
    try:
        creds = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - configuration error path
        raise RuntimeError("GSPREAD_CREDENTIALS must be valid JSON") from exc
    if not isinstance(creds, Mapping):  # pragma: no cover - configuration error path
        raise RuntimeError("GSPREAD_CREDENTIALS JSON must represent an object")
    return creds


def get_client() -> GSpreadClient:
    """Return a cached gspread client authenticated via service-account JSON."""

    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            credentials = _load_credentials()
            log.debug("Authorising gspread client with service-account credentials")
            _CLIENT = gspread.service_account_from_dict(credentials)
    return _CLIENT


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, APIError):
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
        if status in _RETRY_STATUS:
            return True
        text = str(getattr(resp, "text", "") or "")
        detail = str(getattr(exc, "args", [""])[0] or "")
        blob = f"{text} {detail}".lower()
        if "rate limit" in blob or "quota" in blob or "timeout" in blob:
            return True
    if requests_exceptions is not None and isinstance(exc, requests_exceptions.RequestException):
        return True
    return False


def with_backoff(func: Callable[[], T], *, retries: int = 5, base_delay: float = 0.5, max_delay: float = 8.0) -> T:
    """Execute *func* with exponential backoff on transient failures."""

    attempt = 0
    delay = base_delay
    while True:
        try:
            return func()
        except Exception as exc:
            attempt += 1
            if attempt > retries or not _should_retry(exc):
                raise
            sleep_for = min(max_delay, delay) + random.uniform(0.0, base_delay)
            log.warning("Sheets call failed (attempt %s/%s): %s", attempt, retries, exc)
            time.sleep(sleep_for)
            delay *= 2


def get_worksheet(
    spreadsheet_id: str,
    worksheet_name: str,
    *,
    ttl: float = 300.0,
    force: bool = False,
) -> Worksheet:
    """Return a cached worksheet handle, refreshing after *ttl* seconds."""

    now = time.monotonic()
    cache_key = (spreadsheet_id, worksheet_name)
    if not force and ttl > 0:
        cached = _WORKSHEET_CACHE.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.worksheet

    def _open() -> Worksheet:
        spreadsheet = with_backoff(lambda: get_client().open_by_key(spreadsheet_id))
        return with_backoff(lambda: spreadsheet.worksheet(worksheet_name))

    worksheet = _open()
    if ttl > 0:
        _WORKSHEET_CACHE[cache_key] = WorksheetCacheEntry(worksheet=worksheet, expires_at=now + ttl)
    return worksheet


def get_values(
    spreadsheet_id: str,
    worksheet_name: str,
    *,
    ttl: float = 300.0,
    force: bool = False,
) -> Sequence[Sequence[Any]]:
    worksheet = get_worksheet(spreadsheet_id, worksheet_name, ttl=ttl, force=force)
    return with_backoff(lambda: worksheet.get_all_values())


def get_records(
    spreadsheet_id: str,
    worksheet_name: str,
    *,
    ttl: float = 300.0,
    force: bool = False,
) -> Sequence[Mapping[str, Any]]:
    worksheet = get_worksheet(spreadsheet_id, worksheet_name, ttl=ttl, force=force)
    return with_backoff(lambda: worksheet.get_all_records())


def get_config_dict(
    spreadsheet_id: str,
    worksheet_name: str = "Config",
    *,
    ttl: float = 300.0,
    force: bool = False,
) -> Dict[str, str]:
    values = get_values(spreadsheet_id, worksheet_name, ttl=ttl, force=force)
    config: Dict[str, str] = {}
    for row in values:
        if not row:
            continue
        key = str(row[0]).strip() if len(row) >= 1 else ""
        if not key:
            continue
        value = str(row[1]).strip() if len(row) >= 2 else ""
        config[key] = value
    return config


def _resolve_mapping_value(row: Mapping[str, Any], key: str, *, casefold: bool) -> Any:
    if key in row:
        return row[key]
    if casefold:
        target = key.casefold()
        for rk, value in row.items():
            if isinstance(rk, str) and rk.casefold() == target:
                return value
    return ""


def upsert_row(
    spreadsheet_id: str,
    worksheet_name: str,
    row: Mapping[str, Any],
    *,
    key_columns: Sequence[str],
    value_input_option: str = "RAW",
    casefold: bool = True,
    ttl: float = 60.0,
) -> str:
    """Insert or update *row* identified by *key_columns*.

    Returns "inserted" when a new row is appended or "updated" when the row existed.
    """

    if not key_columns:
        raise ValueError("key_columns must not be empty")

    worksheet = get_worksheet(spreadsheet_id, worksheet_name, ttl=ttl)
    values = with_backoff(lambda: worksheet.get_all_values())
    if not values:
        raise RuntimeError(
            f"Worksheet '{worksheet_name}' in spreadsheet '{spreadsheet_id}' is missing a header row"
        )

    header = [cell.strip() for cell in values[0]]
    lookup: Dict[str, int] = {}
    for idx, col in enumerate(header):
        key = col.casefold() if casefold else col
        if key and key not in lookup:
            lookup[key] = idx

    key_values: list[str] = []
    for key in key_columns:
        search_key = key.casefold() if casefold else key
        idx = lookup.get(search_key)
        if idx is None:
            raise KeyError(f"Column '{key}' not present in worksheet '{worksheet_name}' header")
        value = _resolve_mapping_value(row, key, casefold=casefold)
        if value is None:
            value = ""
        value = str(value).strip()
        key_values.append(value.casefold() if casefold else value)
    resolved_key: Tuple[str, ...] = tuple(key_values)
    if all(not part for part in resolved_key):
        raise ValueError("Key column values must not all be empty")

    target_row_index: Optional[int] = None
    for idx, existing in enumerate(values[1:], start=2):
        current: list[str] = []
        for key in key_columns:
            lookup_key = key.casefold() if casefold else key
            col_idx = lookup.get(lookup_key)
            cell = existing[col_idx] if col_idx is not None and col_idx < len(existing) else ""
            cell = str(cell).strip()
            current.append(cell.casefold() if casefold else cell)
        if tuple(current) == resolved_key:
            target_row_index = idx
            break

    ordered_values = []
    for col in header:
        value = _resolve_mapping_value(row, col, casefold=casefold)
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(v) for v in value)
        if value is None:
            value = ""
        ordered_values.append(str(value))

    if target_row_index is not None:
        start = rowcol_to_a1(target_row_index, 1)
        end = rowcol_to_a1(target_row_index, len(ordered_values))
        cell_range = f"{start}:{end}" if len(ordered_values) > 1 else start
        with_backoff(
            lambda: worksheet.update(cell_range, [ordered_values], value_input_option=value_input_option)
        )
        return "updated"

    with_backoff(lambda: worksheet.append_row(ordered_values, value_input_option=value_input_option))
    return "inserted"
