"""
Capabilities registry exposed to CoreOps.
Each bucket entry yields: ttl_sec, last_refresh_at, next_refresh_at, refresh()
"""

from __future__ import annotations

from typing import Any, Dict
from shared.sheets.cache_service import cache as _cache

def capabilities() -> Dict[str, Dict[str, Any]]:
    return _cache.capabilities()
