"""Instrumentation helpers for CoreOps scheduled jobs."""

from __future__ import annotations

import asyncio
import datetime as dt
import functools
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional

log = logging.getLogger("c1c.cron")
TAG = "[cron]"
_RETENTION_DAYS = 2
_METRICS: dict[str, list[dict[str, Any]]] = {}
_LOCK = asyncio.Lock()


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _normalize_rows(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value)
    return None


async def _append_metric(job: str, payload: Dict[str, Any]) -> None:
    cutoff = _now_utc() - dt.timedelta(days=_RETENTION_DAYS)
    async with _LOCK:
        entries = _METRICS.setdefault(job, [])
        entries.append(payload)
        _METRICS[job] = [
            entry
            for entry in entries
            if dt.datetime.fromisoformat(entry["ts"]) >= cutoff
        ]


def cron_task(name: str, scope_fn: Optional[Callable[..., str]] = None):
    """
    Decorator to emit start/result logs and persist metrics for scheduled jobs.
    The decorated coroutine may return {"rows": int, ...} for richer result logs.
    Optionally provide scope_fn(*args, **kwargs) -> str to describe run scope.
    """

    def _wrap(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def _inner(*args, **kwargs):
            scope = ""
            if scope_fn:
                try:
                    scope = scope_fn(*args, **kwargs) or ""
                except Exception:  # pragma: no cover - defensive guard
                    scope = ""
            scope_part = f" scope={scope}" if scope else ""
            started_at = _now_utc()
            log.info(f"{TAG} start job={name}{scope_part}")
            ok = True
            rows: Optional[int] = None
            retries = kwargs.get("retries", 0) or 0
            err: Optional[BaseException] = None
            try:
                result = await fn(*args, **kwargs)
                if isinstance(result, dict):
                    rows = _normalize_rows(result.get("rows"))
                return result
            except Exception as exc:  # pragma: no cover - propagate but log
                ok = False
                err = exc
                raise
            finally:
                finished = _now_utc()
                dur_ms = int((finished - started_at).total_seconds() * 1000)
                payload = {
                    "ts": started_at.isoformat(),
                    "ok": ok,
                    "dur_ms": dur_ms,
                    "rows": rows,
                    "retries": retries,
                }
                try:
                    await _append_metric(name, payload)
                except Exception:  # pragma: no cover - metrics are best-effort
                    log.warning(
                        f"{TAG} metrics_write_failed job={name}",
                        exc_info=True,
                    )
                rows_text = "-" if rows is None else str(rows)
                if ok:
                    log.info(
                        f"{TAG} result job={name} ok=true dur_ms={dur_ms} "
                        f"rows={rows_text} retries={retries}"
                    )
                else:
                    err_type = type(err).__name__ if err else "Error"
                    log.error(
                        f"{TAG} result job={name} ok=false dur_ms={dur_ms} "
                        f"retries={retries} err={err_type}: {err}",
                    )
                    log.debug("".join(traceback.format_exc()))

        return _inner

    return _wrap


async def read_metrics(job: str) -> list[dict[str, Any]]:
    async with _LOCK:
        return list(_METRICS.get(job, []))
