"""Public cache telemetry wrapper for CoreOps and shared tooling."""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from shared.sheets import cache_service
from shared.utils import humanize_duration

UTC = dt.timezone.utc


@dataclass(frozen=True)
class CacheSnapshot:
    """Immutable view of a cache bucket's telemetry."""

    name: str
    available: bool
    ttl_seconds: Optional[int]
    ttl_human: Optional[str]
    last_refresh_at: Optional[dt.datetime]
    age_seconds: Optional[int]
    age_human: Optional[str]
    next_refresh_at: Optional[dt.datetime]
    next_refresh_delta_seconds: Optional[int]
    next_refresh_human: Optional[str]
    last_result: Optional[str]
    last_error: Optional[str]


@dataclass(frozen=True)
class RefreshResult:
    """Result metadata for a manual refresh attempt."""

    name: str
    ok: bool
    duration_ms: Optional[int]
    error: Optional[str]
    snapshot: CacheSnapshot


def _now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def _normalize_datetime(value: object) -> Optional[dt.datetime]:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return None


def _to_int(value: object) -> Optional[int]:
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _clean_text(value: object) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _build_snapshot(name: str, raw: Optional[Dict[str, object]]) -> CacheSnapshot:
    available = isinstance(raw, dict)
    ttl_seconds = _to_int(raw.get("ttl_sec")) if available else None
    last_refresh_at = _normalize_datetime(raw.get("last_refresh_at")) if available else None
    next_refresh_at = _normalize_datetime(raw.get("next_refresh_at")) if available else None
    last_result = _clean_text(raw.get("last_result")) if available else None
    last_error = _clean_text(raw.get("last_error")) if available else None

    now = _now_utc()
    age_seconds: Optional[int] = None
    if last_refresh_at is not None:
        try:
            delta = now - last_refresh_at
            age_seconds = max(0, int(delta.total_seconds()))
        except Exception:
            age_seconds = None

    next_delta: Optional[int] = None
    if next_refresh_at is not None:
        try:
            delta = next_refresh_at - now
            next_delta = int(delta.total_seconds())
        except Exception:
            next_delta = None

    ttl_human = humanize_duration(ttl_seconds) if ttl_seconds is not None else None
    age_human = humanize_duration(age_seconds) if age_seconds is not None else None
    next_human = None
    if next_delta is not None:
        next_human = humanize_duration(abs(next_delta))

    return CacheSnapshot(
        name=name,
        available=available,
        ttl_seconds=ttl_seconds,
        ttl_human=ttl_human,
        last_refresh_at=last_refresh_at,
        age_seconds=age_seconds,
        age_human=age_human,
        next_refresh_at=next_refresh_at,
        next_refresh_delta_seconds=next_delta,
        next_refresh_human=next_human,
        last_result=last_result,
        last_error=last_error,
    )


def list_buckets() -> List[str]:
    """Return the registered bucket names (fail-soft)."""

    try:
        caps = cache_service.capabilities()
    except Exception:
        return []
    names: List[str] = []
    for key in caps.keys():
        if isinstance(key, str):
            names.append(key)
    return sorted(names)


def get_snapshot(name: str) -> CacheSnapshot:
    """Return telemetry snapshot for ``name`` (fail-soft)."""

    raw: Optional[Dict[str, object]] = None
    try:
        data = cache_service.get_bucket_snapshot(name)
    except Exception:
        data = None
    if isinstance(data, dict):
        raw = data
    return _build_snapshot(name, raw)


def get_all_snapshots() -> Dict[str, CacheSnapshot]:
    """Return telemetry snapshots for all known buckets."""

    try:
        caps = cache_service.capabilities()
    except Exception:
        caps = {}

    snapshots: Dict[str, CacheSnapshot] = {}
    for key in caps.keys():
        if not isinstance(key, str):
            continue
        snapshots[key] = get_snapshot(key)
    return snapshots


async def refresh_now(name: str, actor: Optional[str] = None) -> RefreshResult:
    """Trigger an immediate refresh and return result metadata.

    Notes:
        Some cache loaders record failures in the bucket snapshot (last_result/last_error)
        without raising. We therefore inspect the snapshot after the call and flip `ok`
        accordingly to avoid reporting a false success.
    """

    start = time.monotonic()
    error_text: Optional[str] = None
    ok = True
    try:
        await cache_service.cache.refresh_now(name, trigger="manual", actor=actor)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        ok = False
        error_text = (str(exc).strip()) or exc.__class__.__name__
    duration_ms = int((time.monotonic() - start) * 1000)
    snapshot = get_snapshot(name)
    if ok:
        last_error = snapshot.last_error or ""
        last_result = snapshot.last_result or ""
        last_result_norm = last_result.lower()
        if last_error or last_result_norm.startswith("fail"):
            ok = False
            error_text = last_error or last_result or "fail"
    return RefreshResult(
        name=name,
        ok=ok,
        duration_ms=duration_ms,
        error=error_text,
        snapshot=snapshot,
    )
