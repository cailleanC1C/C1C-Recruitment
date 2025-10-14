"""Onboarding (Welcome Crew) sheet helpers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from shared.sheets import core

CONFIG_TAB = "Config"
WELCOME_TICKETS_KEY = "WELCOME_TICKETS_TAB"
PROMO_TICKETS_KEY = "PROMO_TICKETS_TAB"
CLANLIST_KEY = "CLANLIST_TAB"
CONFIG_CACHE_TTL = 300.0
DATA_CACHE_TTL = 180.0
CLAN_TAG_CACHE_TTL = 900.0


@dataclass
class _CacheEntry:
    data: Any
    expires_at: float


_config_cache: Optional[_CacheEntry] = None
_clan_tags_cache: Optional[_CacheEntry] = None


def _get_sheet_id() -> str:
    sheet_id = os.getenv("ONBOARDING_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("ONBOARDING_SHEET_ID environment variable is required")
    return sheet_id


def clear_caches() -> None:
    global _config_cache, _clan_tags_cache
    _config_cache = None
    _clan_tags_cache = None


def _load_config(force: bool = False) -> Dict[str, str]:
    global _config_cache
    now = time.monotonic()
    if not force and _config_cache and _config_cache.expires_at > now:
        return dict(_config_cache.data)
    config = core.get_config_dict(_get_sheet_id(), CONFIG_TAB, ttl=CONFIG_CACHE_TTL, force=force)
    _config_cache = _CacheEntry(data=config, expires_at=now + CONFIG_CACHE_TTL)
    return dict(config)


def _get_config_value(key: str) -> str:
    config = _load_config()
    value = config.get(key, "").strip()
    if not value:
        raise KeyError(f"Config entry '{key}' missing from onboarding Config tab")
    return value


def _dedupe_sheet(tab: str, *, key_columns: Sequence[str]) -> int:
    sheet_id = _get_sheet_id()
    worksheet = core.get_worksheet(sheet_id, tab, ttl=DATA_CACHE_TTL)
    values = core.with_backoff(lambda: worksheet.get_all_values())
    if len(values) <= 1:
        return 0

    header = [cell.strip() for cell in values[0]]
    lookup = {cell.casefold(): idx for idx, cell in enumerate(header)}
    seen: Dict[tuple[str, ...], int] = {}
    duplicates: List[int] = []

    for idx, row in enumerate(values[1:], start=2):
        parts: List[str] = []
        for key in key_columns:
            key_norm = key.casefold()
            col_idx = lookup.get(key_norm)
            if col_idx is None:
                raise KeyError(f"Column '{key}' missing from worksheet '{tab}' header")
            cell = row[col_idx] if col_idx < len(row) else ""
            parts.append(str(cell).strip().casefold())
        if not any(parts):
            continue
        tuple_key = tuple(parts)
        if tuple_key in seen:
            duplicates.append(idx)
        else:
            seen[tuple_key] = idx

    deleted = 0
    for row_index in sorted(duplicates, reverse=True):
        core.with_backoff(lambda idx=row_index: worksheet.delete_rows(idx))
        deleted += 1

    if deleted:
        core.clear_cached_worksheets(sheet_id)
    return deleted


def dedupe(target: str = "welcome") -> int:
    target_norm = target.lower().strip()
    if target_norm not in {"welcome", "promo"}:
        raise ValueError("target must be either 'welcome' or 'promo'")
    if target_norm == "welcome":
        tab = _get_config_value(WELCOME_TICKETS_KEY)
        keys = ["Ticket Number"]
    else:
        tab = _get_config_value(PROMO_TICKETS_KEY)
        keys = ["Ticket Number", "Type", "Thread Created"]
    return _dedupe_sheet(tab, key_columns=keys)


def upsert_welcome(
    row: Mapping[str, Any],
    *,
    key_columns: Sequence[str] | None = None,
    value_input_option: str = "RAW",
) -> str:
    sheet_id = _get_sheet_id()
    tab = _get_config_value(WELCOME_TICKETS_KEY)
    keys = list(key_columns) if key_columns else ["Ticket Number"]
    return core.upsert_row(
        sheet_id,
        tab,
        row,
        key_columns=keys,
        value_input_option=value_input_option,
        ttl=DATA_CACHE_TTL,
    )


def upsert_promo(
    row: Mapping[str, Any],
    *,
    key_columns: Sequence[str] | None = None,
    value_input_option: str = "RAW",
) -> str:
    sheet_id = _get_sheet_id()
    tab = _get_config_value(PROMO_TICKETS_KEY)
    keys = list(key_columns) if key_columns else ["Ticket Number", "Type", "Thread Created"]
    return core.upsert_row(
        sheet_id,
        tab,
        row,
        key_columns=keys,
        value_input_option=value_input_option,
        ttl=DATA_CACHE_TTL,
    )


def load_clan_tags(*, force: bool = False) -> Sequence[str]:
    global _clan_tags_cache
    now = time.monotonic()
    if not force and _clan_tags_cache and _clan_tags_cache.expires_at > now:
        return list(_clan_tags_cache.data)

    sheet_id = _get_sheet_id()
    tab = _get_config_value(CLANLIST_KEY)
    values = core.get_values(sheet_id, tab, ttl=DATA_CACHE_TTL, force=force)
    if not values:
        _clan_tags_cache = _CacheEntry(data=[], expires_at=now + CLAN_TAG_CACHE_TTL)
        return []

    header = [cell.strip().lower() for cell in values[0]]
    col_idx = 0
    for candidate in ("clantag", "tag", "abbr", "code"):
        if candidate in header:
            col_idx = header.index(candidate)
            break
    tags: List[str] = []
    for row in values[1:]:
        cell = row[col_idx] if col_idx < len(row) else ""
        tag = str(cell or "").strip().upper()
        if tag:
            tags.append(tag)

    deduped = list(dict.fromkeys(tags))
    _clan_tags_cache = _CacheEntry(data=deduped, expires_at=now + CLAN_TAG_CACHE_TTL)
    return list(deduped)


__all__ = [
    "clear_caches",
    "dedupe",
    "load_clan_tags",
    "upsert_promo",
    "upsert_welcome",
]
