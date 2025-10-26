"""Recruitment-specific Google Sheets accessors."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, cast

from shared.sheets import core
from shared.sheets.async_core import afetch_records, afetch_values
from shared.sheets.cache_service import cache

_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))
_CONFIG_TTL = int(os.getenv("SHEETS_CONFIG_CACHE_TTL_SEC", str(_CACHE_TTL)))

_CONFIG_CACHE: Dict[str, str] | None = None
_CONFIG_CACHE_TS: float = 0.0

_CLAN_ROWS: List[List[str]] | None = None
_CLAN_ROWS_TS: float = 0.0
_CLAN_TAG_INDEX: Dict[str, List[str]] | None = None
_CLAN_TAG_INDEX_TS: float = 0.0

_TEMPLATE_ROWS: List[Dict[str, Any]] | None = None
_TEMPLATE_ROWS_TS: float = 0.0


def _sheet_id() -> str:
    sheet_id = (
        os.getenv("RECRUITMENT_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    ).strip()
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID not set")
    return sheet_id


def _ensure_service_account_credentials() -> None:
    creds = (
        os.getenv("GSPREAD_CREDENTIALS")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or ""
    ).strip()
    if not creds:
        raise RuntimeError("GSPREAD_CREDENTIALS not set")


def _config_tab() -> str:
    return os.getenv("RECRUITMENT_CONFIG_TAB", "Config")


def _load_config(force: bool = False) -> Dict[str, str]:
    global _CONFIG_CACHE, _CONFIG_CACHE_TS
    now = time.time()
    if not force and _CONFIG_CACHE and (now - _CONFIG_CACHE_TS) < _CONFIG_TTL:
        return _CONFIG_CACHE

    records = core.fetch_records(_sheet_id(), _config_tab())
    parsed: Dict[str, str] = {}
    for row in records:
        key_value: Optional[str] = None
        stored_value: Optional[str] = None
        for col, value in row.items():
            col_norm = (col or "").strip().lower()
            if col_norm == "key":
                key_value = str(value).strip().lower() if value is not None else ""
            elif col_norm in {"value", "val"}:
                stored_value = str(value).strip() if value is not None else ""
        if key_value:
            if stored_value:
                parsed[key_value] = stored_value
                continue
            for col, value in row.items():
                if (col or "").strip().lower() == "key":
                    continue
                if value is None:
                    continue
                candidate = str(value).strip()
                if candidate:
                    parsed[key_value] = candidate
                    break

    _CONFIG_CACHE = parsed
    _CONFIG_CACHE_TS = now
    return parsed


def _config_lookup(key: str, default: Optional[str] = None) -> Optional[str]:
    want = (key or "").strip().lower()
    if not want:
        return default
    config = _load_config()
    return config.get(want, default)


def _clans_tab() -> str:
    return _config_lookup("clans_tab", os.getenv("WORKSHEET_NAME", "bot_info")) or "bot_info"


def _templates_tab() -> str:
    return _config_lookup("welcome_templates_tab", "WelcomeTemplates") or "WelcomeTemplates"


def _sanitize_clan_rows(raw_rows: List[List[str]]) -> List[List[str]]:
    """Drop header rows and blank entries from ``raw_rows``."""

    def _norm(value: Any) -> str:
        return str(value).strip().upper() if value is not None else ""

    cleaned: List[List[str]] = []
    for row in raw_rows[3:]:  # Sheet headers occupy rows 1–3.
        if not row:
            continue
        name = _norm(row[1] if len(row) > 1 else "")
        tag = _norm(row[2] if len(row) > 2 else "")
        roster = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
        if not name and not tag:
            continue
        if name in {"CLAN", "CLAN NAME", "CLANS"}:
            continue
        if tag in {"TAG", "CLAN TAG", "CLAN"}:
            continue
        if not roster:
            continue
        cleaned.append(row)
    return cleaned


def fetch_clans(force: bool = False) -> List[List[str]]:
    """Fetch the recruitment clan matrix from Sheets."""

    global _CLAN_ROWS, _CLAN_ROWS_TS, _CLAN_TAG_INDEX, _CLAN_TAG_INDEX_TS
    now = time.time()
    if not force and _CLAN_ROWS and (now - _CLAN_ROWS_TS) < _CACHE_TTL:
        if _CLAN_TAG_INDEX is None:
            _CLAN_TAG_INDEX = _build_tag_index(_CLAN_ROWS)
            _CLAN_TAG_INDEX_TS = _CLAN_ROWS_TS
        return _CLAN_ROWS

    rows = core.fetch_values(_sheet_id(), _clans_tab())
    sanitized = _sanitize_clan_rows(rows)
    _CLAN_ROWS = sanitized
    _CLAN_ROWS_TS = now
    _CLAN_TAG_INDEX = _build_tag_index(sanitized)
    _CLAN_TAG_INDEX_TS = now
    return sanitized


def fetch_templates(force: bool = False) -> List[Dict[str, Any]]:
    """Fetch welcome templates for recruitment flows."""

    global _TEMPLATE_ROWS, _TEMPLATE_ROWS_TS
    now = time.time()
    if not force and _TEMPLATE_ROWS and (now - _TEMPLATE_ROWS_TS) < _CACHE_TTL:
        return _TEMPLATE_ROWS

    rows = core.fetch_records(_sheet_id(), _templates_tab())
    _TEMPLATE_ROWS = rows
    _TEMPLATE_ROWS_TS = now
    return rows


def fetch_clan_rows(force: bool = False) -> List[List[str]]:
    """Backward-compatible alias for legacy imports."""

    return fetch_clans(force=force)


def fetch_welcome_templates(tab: str | None = None) -> List[Dict[str, Any]]:
    """Backward-compatible alias retaining the previous signature."""

    if tab:
        return core.fetch_records(_sheet_id(), tab)
    return fetch_templates()


def get_cached_welcome_templates() -> List[Dict[str, Any]]:
    """Return cached WelcomeTemplates rows when available, falling back to a live fetch."""

    bucket = cache.get_bucket("templates")
    if bucket and bucket.value is not None:
        return cast(List[Dict[str, Any]], bucket.value)
    return fetch_welcome_templates()


# -----------------------------
# Phase 3 cache registrations
# -----------------------------
_TTL_CLANS_SEC = 3 * 60 * 60
_TTL_TEMPLATES_SEC = 7 * 24 * 60 * 60


async def _load_clans_async() -> List[List[str]]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _clans_tab()
    rows = await afetch_values(sheet_id, tab)
    return _sanitize_clan_rows(rows)


async def _load_templates_async() -> List[Dict[str, Any]]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _templates_tab()
    return await afetch_records(sheet_id, tab)


cache.register("clans", _TTL_CLANS_SEC, _load_clans_async)
cache.register("templates", _TTL_TEMPLATES_SEC, _load_templates_async)


def _normalize_tag(tag: str | None) -> str:
    text = "" if tag is None else str(tag).strip().upper()
    return "".join(ch for ch in text if ch.isalnum())


def _build_tag_index(rows: List[List[str]]) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for row in rows:
        if len(row) < 3:
            continue
        normalized = _normalize_tag(row[2])
        if not normalized:
            continue
        index[normalized] = row
    return index


def fetch_clan_tags_index(force: bool = False) -> Dict[str, List[str]]:
    """Return a cached mapping of ``TAG`` → clan row."""

    global _CLAN_TAG_INDEX, _CLAN_TAG_INDEX_TS
    now = time.time()
    if force or _CLAN_TAG_INDEX is None or (now - _CLAN_TAG_INDEX_TS) >= _CACHE_TTL:
        rows = fetch_clans(force=force)
        _CLAN_TAG_INDEX = _build_tag_index(rows)
        _CLAN_TAG_INDEX_TS = time.time()
    return _CLAN_TAG_INDEX or {}


def get_clan_by_tag(tag: str, *, force: bool = False) -> List[str] | None:
    """Lookup a clan row by tag using the cached index when available."""

    normalized = _normalize_tag(tag)
    if not normalized:
        return None

    index = fetch_clan_tags_index(force=force)
    if index:
        return index.get(normalized)

    # Index unavailable — fall back to a lightweight scan of cached rows.
    rows = fetch_clans(force=False)
    for row in rows:
        if len(row) < 3:
            continue
        if _normalize_tag(row[2]) == normalized:
            return row
    return None
