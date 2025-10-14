"""Recruitment-specific Google Sheets accessors."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from shared.sheets import core

_CACHE_ROWS: List[List[str]] | None = None
_CACHE_ROWS_TS: float = 0.0
_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))


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


def fetch_welcome_templates(tab: str | None = None) -> List[Dict[str, Any]]:
    sheet = core.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    tab = tab or os.getenv("WELCOME_SHEET_TAB", "WelcomeTemplates")
    ws = sheet.worksheet(tab)
    return ws.get_all_records()
