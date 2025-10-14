"""Recruitment-specific Google Sheets accessors."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from shared.sheets import core

_CACHE_ROWS: List[List[str]] | None = None
_CACHE_ROWS_TS: float = 0.0
_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))

_CONFIG_ROWS: List[Dict[str, Any]] | None = None
_CONFIG_ROWS_TS: float = 0.0


def _config_tab_name() -> str:
    return os.getenv("SHEET_CONFIG_TAB", "Config")


def _worksheet_name() -> str:
    return os.getenv("WORKSHEET_NAME", "bot_info")


def fetch_clan_rows(force: bool = False) -> List[List[str]]:
    global _CACHE_ROWS, _CACHE_ROWS_TS
    now = time.time()
    if not force and _CACHE_ROWS and (now - _CACHE_ROWS_TS) < _CACHE_TTL:
        return _CACHE_ROWS
    sheet = core.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    ws = sheet.worksheet(_worksheet_name())
    _CACHE_ROWS = ws.get_all_values()
    _CACHE_ROWS_TS = now
    return _CACHE_ROWS


def _config_rows(force: bool = False) -> List[Dict[str, Any]]:
    global _CONFIG_ROWS, _CONFIG_ROWS_TS
    now = time.time()
    if not force and _CONFIG_ROWS and (now - _CONFIG_ROWS_TS) < _CACHE_TTL:
        return _CONFIG_ROWS
    sheet = core.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    ws = sheet.worksheet(_config_tab_name())
    _CONFIG_ROWS = ws.get_all_records()
    _CONFIG_ROWS_TS = now
    return _CONFIG_ROWS


def _config_lookup(key: str, default: Optional[str] = None) -> Optional[str]:
    want = (key or "").strip().lower()
    if not want:
        return default
    rows = _config_rows()
    for row in rows:
        row_key: Optional[str] = None
        row_value: Optional[str] = None
        for col, value in row.items():
            col_norm = (col or "").strip().lower()
            if col_norm == "key":
                row_key = str(value).strip().lower() if value is not None else ""
            elif col_norm in {"value", "val"}:
                row_value = str(value).strip() if value is not None else ""
        if row_key == want:
            if row_value:
                return row_value
            for col, value in row.items():
                col_norm = (col or "").strip().lower()
                if col_norm == "key":
                    continue
                if value is None:
                    continue
                candidate = str(value).strip()
                if candidate:
                    return candidate
            return default
    return default


def _welcome_tab_name() -> str:
    for key in (
        "welcome_templates_tab",
        "welcome_template_tab",
        "welcome_tab",
        "welcome_templates",
    ):
        value = _config_lookup(key)
        if value:
            return value
    return "WelcomeTemplates"


def fetch_welcome_templates(tab: str | None = None) -> List[Dict[str, Any]]:
    sheet = core.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    tab_name = tab or _welcome_tab_name()
    ws = sheet.worksheet(tab_name)
    return ws.get_all_records()
