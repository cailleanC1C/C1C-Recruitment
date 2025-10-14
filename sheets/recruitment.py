"""Recruitment sheet helpers (tabs configured via the Config worksheet)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from shared.sheets import core

CONFIG_TAB = "Config"
CLANS_TAB_KEY = "CLANS_TAB"
TEMPLATES_TAB_KEY = "WELCOME_TEMPLATES_TAB"
CONFIG_CACHE_TTL = 300.0
DATA_CACHE_TTL = 180.0


@dataclass
class _CacheEntry:
    data: Any
    expires_at: float


_config_cache: Optional[_CacheEntry] = None
_clans_cache: Optional[_CacheEntry] = None
_templates_cache: Optional[_CacheEntry] = None


def _get_sheet_id() -> str:
    sheet_id = os.getenv("RECRUITMENT_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID environment variable is required")
    return sheet_id


def clear_caches() -> None:
    global _config_cache, _clans_cache, _templates_cache
    _config_cache = None
    _clans_cache = None
    _templates_cache = None


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
    if key not in config or not config[key]:
        raise KeyError(f"Config entry '{key}' missing from recruitment Config tab")
    return config[key]


def fetch_clans(*, ttl: float = DATA_CACHE_TTL, force: bool = False) -> Sequence[Mapping[str, Any]]:
    global _clans_cache
    now = time.monotonic()
    if not force and _clans_cache and _clans_cache.expires_at > now:
        return list(_clans_cache.data)

    sheet_id = _get_sheet_id()
    tab = _get_config_value(CLANS_TAB_KEY)
    records = list(core.get_records(sheet_id, tab, ttl=ttl, force=force))
    if ttl > 0:
        _clans_cache = _CacheEntry(data=records, expires_at=now + ttl)
    else:
        _clans_cache = None
    return list(records)


def fetch_templates(*, ttl: float = DATA_CACHE_TTL, force: bool = False) -> Sequence[Mapping[str, Any]]:
    global _templates_cache
    now = time.monotonic()
    if not force and _templates_cache and _templates_cache.expires_at > now:
        return list(_templates_cache.data)

    sheet_id = _get_sheet_id()
    tab = _get_config_value(TEMPLATES_TAB_KEY)
    records = list(core.get_records(sheet_id, tab, ttl=ttl, force=force))
    if ttl > 0:
        _templates_cache = _CacheEntry(data=records, expires_at=now + ttl)
    else:
        _templates_cache = None
    return list(records)


__all__ = [
    "clear_caches",
    "fetch_clans",
    "fetch_templates",
]
