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
    ttl_sec: Optional[int]
    last_refresh_at: Optional[dt.datetime]
    age_seconds: Optional[int]
    age_human: Optional[str]
    age_sec: Optional[int]
    next_refresh_at: Optional[dt.datetime]
    next_refresh_delta_seconds: Optional[int]
    next_refresh_human: Optional[str]
    last_result: Optional[str]
    last_error: Optional[str]
    retries: Optional[int]
    last_trigger: Optional[str]
    ttl_expired: Optional[bool]
    item_count: Optional[int]


@dataclass(frozen=True)
class RefreshResult:
    """Result metadata for a manual refresh attempt."""

    name: str
    ok: bool
    duration_ms: Optional[int]
    error: Optional[str]
    retries: Optional[int]
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
    retries = _to_int(raw.get("retries")) if available else None
    last_trigger = _clean_text(raw.get("last_trigger")) if available else None
    ttl_expired: Optional[bool] = None
    if available:
        value = raw.get("ttl_expired")
        if isinstance(value, bool):
            ttl_expired = value
    item_count = _to_int(raw.get("item_count")) if available else None

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
        ttl_sec=ttl_seconds,
        last_refresh_at=last_refresh_at,
        age_seconds=age_seconds,
        age_human=age_human,
        age_sec=age_seconds,
        next_refresh_at=next_refresh_at,
        next_refresh_delta_seconds=next_delta,
        next_refresh_human=next_human,
        last_result=last_result,
        last_error=last_error,
        retries=retries,
        last_trigger=last_trigger,
        ttl_expired=ttl_expired,
        item_count=item_count,
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

    snapshots: Dict[str, CacheSnapshot] = {}
    for name in list_buckets():
        raw: Optional[Dict[str, object]] = None
        try:
            candidate = cache_service.get_bucket_snapshot(name)
        except Exception:
            candidate = None
        if isinstance(candidate, dict):
            raw = candidate
        snapshots[name] = _build_snapshot(name, raw)
    return snapshots


def _format_exception(exc: BaseException) -> str:
    message = str(exc).strip().strip("\"")
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def _normalize_bucket_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("cache bucket name must be non-empty")
    return cleaned


def _derive_error_text(snapshot: CacheSnapshot) -> Optional[str]:
    if snapshot.last_error:
        return snapshot.last_error
    if snapshot.last_result and snapshot.last_result.lower().startswith("fail"):
        return snapshot.last_result
    return None


async def refresh_now(name: str, actor: Optional[str] = None) -> RefreshResult:
    """Trigger an immediate refresh and return result metadata.

    Notes:
        Some cache loaders record failures in the bucket snapshot (last_result/last_error)
        without raising. We therefore inspect the snapshot after the call and flip `ok`
        accordingly to avoid reporting a false success.
    """

    bucket = _normalize_bucket_name(name)
    start = time.monotonic()
    error_text: Optional[str] = None
    ok = True
    trigger = "schedule" if actor == "cron" else "manual"
    try:
        await cache_service.cache.refresh_now(bucket, trigger=trigger, actor=actor)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        ok = False
        error_text = _format_exception(exc)
    duration_ms = int((time.monotonic() - start) * 1000)
    snapshot = get_snapshot(bucket)
    retries = snapshot.retries
    if retries is not None:
        try:
            retries = int(retries)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            retries = None
    if ok:
        derived = _derive_error_text(snapshot)
        if derived:
            ok = False
            error_text = derived
    if error_text:
        error_text = error_text.strip().strip("\"")
    return RefreshResult(
        name=bucket,
        ok=ok,
        duration_ms=duration_ms,
        error=error_text,
        retries=retries,
        snapshot=snapshot,
    )
