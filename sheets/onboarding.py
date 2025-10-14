"""Onboarding sheet helpers (Welcome Crew)."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from shared.sheets import core


def fetch_sheet(name: str) -> Any:
    sheet = core.open_by_key(os.getenv("GSHEET_ID") or os.getenv("GOOGLE_SHEET_ID"))
    return sheet.worksheet(name)


def ensure_headers(ws, headers: List[str]) -> None:
    try:
        existing = ws.row_values(1)
    except Exception:
        existing = []
    normalized = [h.strip().lower() for h in existing]
    wanted = [h.strip().lower() for h in headers]
    if normalized != wanted:
        ws.update("A1", [headers])


def fetch_records(ws) -> List[Dict[str, Any]]:
    return ws.get_all_records()
