"""Recruitment-specific Google Sheets accessors."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from shared.sheets import core

_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))
_CONFIG_TTL = int(os.getenv("SHEETS_CONFIG_CACHE_TTL_SEC", str(_CACHE_TTL)))

_CONFIG_CACHE: Dict[str, str] | None = None
_CONFIG_CACHE_TS: float = 0.0

_CLAN_ROWS: List[List[str]] | None = None
_CLAN_ROWS_TS: float = 0.0

_TEMPLATE_ROWS: List[Dict[str, Any]] | None = None
_TEMPLATE_ROWS_TS: float = 0.0


def _sheet_id() -> str:
    sheet_id = (
        os.getenv("RECRUITMENT_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    )
    sheet_id = sheet_id.strip()
    if not sheet_id:
        raise RuntimeError(
            "RECRUITMENT_SHEET_ID/GOOGLE_SHEET_ID/GSHEET_ID not set for recruitment"
        )
    return sheet_id


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


def fetch_clans(force: bool = False) -> List[List[str]]:
    """Fetch the recruitment clan matrix from Sheets."""

    global _CLAN_ROWS, _CLAN_ROWS_TS
    now = time.time()
    if not force and _CLAN_ROWS and (now - _CLAN_ROWS_TS) < _CACHE_TTL:
        return _CLAN_ROWS

    rows = core.fetch_values(_sheet_id(), _clans_tab())
    _CLAN_ROWS = rows
    _CLAN_ROWS_TS = now
    return rows


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
