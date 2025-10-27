"""Onboarding sheet helpers (Welcome Crew)."""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from shared.sheets import core
from shared.sheets.async_core import afetch_values
from shared.sheets.cache_service import cache

_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))
_CONFIG_TTL = int(os.getenv("SHEETS_CONFIG_CACHE_TTL_SEC", str(_CACHE_TTL)))
_CLAN_TAG_TTL = int(os.getenv("CLAN_TAGS_CACHE_TTL_SEC", str(_CACHE_TTL)))

_CONFIG_CACHE: Dict[str, str] | None = None
_CONFIG_CACHE_TS: float = 0.0

_CLAN_TAGS: List[str] | None = None
_CLAN_TAG_TS: float = 0.0


def _sheet_id() -> str:
    sheet_id = (
        os.getenv("ONBOARDING_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    )
    sheet_id = sheet_id.strip()
    if not sheet_id:
        raise RuntimeError("ONBOARDING_SHEET_ID not set")
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
    return os.getenv("ONBOARDING_CONFIG_TAB", "Config")


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


def _resolve_onboarding_sheet_id() -> str:
    """Return the configured onboarding sheet identifier."""

    return _sheet_id()


def _read_onboarding_config(sheet_id: Optional[str] = None) -> Dict[str, str]:
    """Return the onboarding config mapping using upper-case keys.

    ``_load_config`` normalises keys to lower-case for internal use.  Some
    callers expect the sheet's original upper-case key names, so we build a new
    dictionary with upper-case keys while reusing the cached configuration
    values.
    """

    _ = sheet_id  # preserved for API compatibility with older helpers
    config = _load_config()
    return {key.upper(): value for key, value in config.items()}


def _resolve_onboarding_and_welcome_tab() -> Tuple[str, str]:
    """Return the onboarding sheet id and configured welcome tab name."""

    sheet_id = _resolve_onboarding_sheet_id()
    cfg = _read_onboarding_config(sheet_id)
    tab = cfg.get("WELCOME_TICKETS_TAB")
    if not tab:
        raise RuntimeError("Onboarding Config missing WELCOME_TICKETS_TAB")
    return sheet_id, str(tab)


def _resolve_onboarding_and_promo_tab() -> Tuple[str, str]:
    """Return the onboarding sheet id and configured promo tab name."""

    sheet_id = _resolve_onboarding_sheet_id()
    cfg = _read_onboarding_config(sheet_id)
    tab = cfg.get("PROMO_TICKETS_TAB")
    if not tab:
        raise RuntimeError("Onboarding Config missing PROMO_TICKETS_TAB")
    return sheet_id, str(tab)


def _welcome_tab() -> str:
    return (
        _config_lookup("welcome_tickets_tab", "WelcomeTickets")
        or "WelcomeTickets"
    )


def _promo_tab() -> str:
    return (
        _config_lookup("promo_tickets_tab", "PromoTickets")
        or "PromoTickets"
    )


def _resolve_onboarding_and_welcome_tab() -> tuple[str, str]:
    """Return the onboarding sheet ID and configured welcome tab name."""

    return _sheet_id(), _welcome_tab()


def _clanlist_tab() -> str:
    return _config_lookup("clanlist_tab", "ClanList") or "ClanList"


def _worksheet(tab: str):
    return core.get_worksheet(_sheet_id(), tab)


def _resolve_onboarding_and_promo_tab() -> tuple[str, str]:
    """Return the onboarding sheet ID and promo tab name."""

    return _sheet_id(), _promo_tab()
def _resolve_onboarding_and_clanlist_tab() -> Tuple[str, str]:
    """Return the onboarding sheet id and configured clan list tab name."""

    sheet_id = _resolve_onboarding_sheet_id()
    cfg = _read_onboarding_config(sheet_id)
    tab = cfg.get("CLANLIST_TAB")
    if not tab:
        raise RuntimeError("Onboarding Config missing CLANLIST_TAB")
    return sheet_id, str(tab)


def _column_index(headers: Sequence[str], name: str, default: int = 0) -> int:
    target = (name or "").strip().lower()
    for idx, header in enumerate(headers):
        if (header or "").strip().lower() == target:
            return idx
    return default


def _col_to_a1(col_index: int) -> str:
    if col_index < 0:
        raise ValueError("column index must be >= 0")
    letters = ""
    value = col_index
    while True:
        value, remainder = divmod(value, 26)
        letters = chr(ord("A") + remainder) + letters
        if value == 0:
            break
        value -= 1
    return letters


def _ensure_headers(ws, headers: Sequence[str]) -> List[str]:
    desired = [h.strip() for h in headers]
    try:
        existing = core.call_with_backoff(ws.row_values, 1)
    except Exception:
        existing = []
    existing_norm = [h.strip() for h in existing]
    if existing_norm != desired:
        core.call_with_backoff(ws.update, "A1", [list(headers)])
        return list(headers)
    return list(existing) if existing else list(headers)


def _fmt_ticket(ticket: str | None) -> str:
    text = (ticket or "").strip().lstrip("#")
    return text.upper()


def _match_row(
    headers: Sequence[str],
    row: Sequence[str],
    key_columns: Sequence[Tuple[str, Callable[[str | None], str]]],
    candidates: Sequence[str],
) -> bool:
    for (name, formatter), candidate in zip(key_columns, candidates):
        idx = _column_index(headers, name)
        current = row[idx] if idx < len(row) else ""
        if formatter(current) != formatter(candidate):
            return False
    return True


def _upsert(
    ws,
    key_columns: Sequence[Tuple[str, Callable[[str | None], str]]],
    row_values: Sequence[str],
    headers: Sequence[str],
    *,
    search_values: Optional[Sequence[str]] = None,
) -> str:
    header = _ensure_headers(ws, headers)
    total_cols = len(header)
    values = core.call_with_backoff(ws.get_all_values)
    if search_values is None:
        search_values = []
        for name, _ in key_columns:
            idx = _column_index(header, name)
            search_values.append(row_values[idx] if idx < len(row_values) else "")

    for row_idx, row in enumerate(values[1:], start=2):
        if _match_row(header, row, key_columns, search_values):
            end_col = _col_to_a1(total_cols - 1)
            rng = f"A{row_idx}:{end_col}{row_idx}"
            core.call_with_backoff(ws.update, rng, [list(row_values)])
            return "updated"

    core.call_with_backoff(ws.append_row, list(row_values), value_input_option="RAW")
    return "inserted"


def upsert_welcome(row_values: Sequence[str], headers: Sequence[str]) -> str:
    """Insert or update a welcome ticket row based on its ticket number."""

    ws = _worksheet(_welcome_tab())
    keys = [("ticket number", _fmt_ticket)]
    return _upsert(ws, keys, row_values, headers)


def upsert_promo(
    row_values: Sequence[str],
    headers: Sequence[str],
    *,
    ticket: str,
    promo_type: str,
    created: str,
) -> str:
    """Insert or update a promo ticket row based on ticket + type + created."""

    ws = _worksheet(_promo_tab())
    keys = [
        ("ticket number", _fmt_ticket),
        ("type", lambda value: (value or "").strip().lower()),
        ("thread created", lambda value: (value or "").strip()),
    ]
    search = [ticket, promo_type, created]
    return _upsert(ws, keys, row_values, headers, search_values=search)


def dedupe() -> Dict[str, int]:
    """Remove duplicate rows from welcome and promo sheets."""

    results = {
        "welcome": _dedupe_sheet(
            _worksheet(_welcome_tab()),
            key_columns=[("ticket number", _fmt_ticket)],
        ),
        "promo": _dedupe_sheet(
            _worksheet(_promo_tab()),
            key_columns=[
                ("ticket number", _fmt_ticket),
                ("type", lambda value: (value or "").strip().lower()),
                ("thread created", lambda value: (value or "").strip()),
            ],
        ),
    }
    return results


def _collapse_row_ranges(indexes: Sequence[int]) -> List[Tuple[int, int]]:
    if not indexes:
        return []
    ranges: List[Tuple[int, int]] = []
    start = indexes[0]
    prev = indexes[0]
    for idx in indexes[1:]:
        if idx == prev + 1:
            prev = idx
            continue
        ranges.append((start, prev))
        start = idx
        prev = idx
    ranges.append((start, prev))
    return ranges


def _dedupe_sheet(
    ws,
    *,
    key_columns: Sequence[Tuple[str, Callable[[str | None], str]]],
) -> int:
    values = core.call_with_backoff(ws.get_all_values)
    if len(values) <= 1:
        return 0

    header = values[0]
    column_indexes = [_column_index(header, name) for name, _ in key_columns]
    seen: Dict[Tuple[str, ...], int] = {}
    for idx, row in enumerate(values[1:], start=2):
        key_parts: List[str] = []
        for col_index, (_, formatter) in zip(column_indexes, key_columns):
            current = row[col_index] if col_index < len(row) else ""
            key_parts.append(formatter(current))
        key = tuple(key_parts)
        seen[key] = idx  # keep last occurrence

    keep_rows = set(seen.values())
    to_delete = [
        row_idx
        for row_idx in range(2, len(values) + 1)
        if row_idx not in keep_rows
    ]
    if not to_delete:
        return 0

    ranges = _collapse_row_ranges(sorted(to_delete))
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "ROWS",
                    "startIndex": start - 1,
                    "endIndex": end,
                }
            }
        }
        for start, end in reversed(ranges)
    ]

    deleted = 0
    try:
        core.call_with_backoff(ws.spreadsheet.batch_update, {"requests": requests})
        for start, end in ranges:
            deleted += end - start + 1
        return deleted
    except Exception:
        pass

    # Fallback to per-row deletes if batch update fails.
    for row_idx in sorted(to_delete, reverse=True):
        try:
            core.call_with_backoff(ws.delete_rows, row_idx)
            deleted += 1
        except Exception:
            continue
    return deleted


def load_clan_tags(force: bool = False) -> List[str]:
    """Load and cache clan tags from the configured clan list tab."""

    global _CLAN_TAGS, _CLAN_TAG_TS
    now = time.time()
    if not force and _CLAN_TAGS and (now - _CLAN_TAG_TS) < _CLAN_TAG_TTL:
        return _CLAN_TAGS

    values = core.fetch_values(_sheet_id(), _clanlist_tab())
    tags: List[str] = []
    for row in values[1:]:
        if not row:
            continue
        tag = (row[0] if len(row) > 0 else "").strip().upper()
        if tag:
            tags.append(tag)

    _CLAN_TAGS = tags
    _CLAN_TAG_TS = now
    return tags


# -----------------------------
# Phase 3 cache registrations
# -----------------------------
_TTL_CLAN_TAGS_SEC = 7 * 24 * 60 * 60


async def _load_clan_tags_async() -> List[str]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _clanlist_tab()
    values = await afetch_values(sheet_id, tab)
    tags: List[str] = []
    for row in values[1:]:
        if not row:
            continue
        tag = (row[0] if len(row) > 0 else "").strip().upper()
        if tag:
            tags.append(tag)
    return tags


cache.register("clan_tags", _TTL_CLAN_TAGS_SEC, _load_clan_tags_async)
