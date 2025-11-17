"""Shared logging helpers for lifecycle events."""

from __future__ import annotations

from time import monotonic
from typing import Any

__all__ = ["log_lifecycle"]


_lifecycle_dedupe: dict[tuple[str, str], float] = {}


def _fmt_kvs(kvs: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in kvs.items():
        if value in (None, "", "-", False, 0, {}, []):
            continue
        parts.append(f"{key}={value}")
    return " • ".join(parts)


def log_lifecycle(logger: Any, scope: str, event: str, **fields: Any) -> None:
    """Log a human-readable lifecycle line with dedupe and blank-field filtering.

    Parameters
    ----------
    logger:
        Logger-like object exposing ``info``.
    scope:
        High-level component scope (e.g. ``"onboarding"``).
    event:
        Lifecycle event name (e.g. ``"view_registered"``).
    **fields:
        Additional key/value pairs rendered into the log line. Blank or falsey
        values (``None``, empty strings, ``-``, ``False``, ``0``, empty
        containers) are omitted automatically.

    The helper enforces a 5-second dedupe window per ``(scope, event)`` pair to
    avoid noisy repeat lines during startup races.
    """

    now = monotonic()
    key = (scope, event)
    last = _lifecycle_dedupe.get(key, 0.0)
    if now - last < 5.0:
        return
    _lifecycle_dedupe[key] = now

    prefix = "📘"
    title = f"{scope.capitalize()} watcher"
    kv_text = _fmt_kvs(fields)
    line = f"{prefix} {title} — event={event}" + (f" • {kv_text}" if kv_text else "")
    try:
        logger.info(line)
    except Exception:
        # Logging should never raise upstream.
        pass
