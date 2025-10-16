from __future__ import annotations

"""
Async wrappers for Google Sheets access.

This module mirrors the sync API in shared.sheets.core, but routes every call
through asyncio.to_thread and uses async-friendly retry backoff so the Discord
event loop never blocks.

Non-breaking: existing callers can keep using shared.sheets.core.
New/ported code should import from shared.sheets.async_core.
"""

import asyncio
from typing import Any, Callable, TypeVar, ParamSpec

from . import core as _core

P = ParamSpec("P")
T = TypeVar("T")

# Defaults mirror shared.sheets.core.
_DEFAULT_ATTEMPTS = 6
_DEFAULT_BASE = 0.25  # seconds
_DEFAULT_FACTOR = 1.8  # multiplier


async def _retry_with_backoff_async(
    func: Callable[P, T],
    *args: P.args,
    attempts: int | None = None,
    base_delay: float | None = None,
    factor: float | None = None,
    **kwargs: P.kwargs,
) -> T:
    """
    Async retry wrapper: runs the sync func in a worker thread and backs off with
    await asyncio.sleep(...). Never blocks the event loop.
    """
    max_attempts, base, mult = _DEFAULT_ATTEMPTS, _DEFAULT_BASE, _DEFAULT_FACTOR
    if attempts is not None:
        max_attempts = attempts
    if base_delay is not None:
        base = base_delay
    if factor is not None:
        mult = factor

    last_exc: BaseException | None = None
    delay = base
    for attempt in range(1, max_attempts + 1):
        try:
            # Execute the sync function in a thread
            return await asyncio.to_thread(func, *args, **kwargs)
        except BaseException as e:  # gspread raises various exceptions
            # Respect task cancellation — don't swallow CancelledError
            if isinstance(e, asyncio.CancelledError):
                raise
            last_exc = e
            if attempt >= max_attempts:
                break
            # Jitter-friendly exponential backoff (cap reasonable upper bound)
            await asyncio.sleep(min(delay, 10.0))
            delay *= mult

    assert last_exc is not None
    raise last_exc


# -------------------------
# Async mirrors of core API
# -------------------------

async def aopen_by_key(sheet_id: str | None = None):
    """Async: open spreadsheet by key (handle cached in core)."""
    return await asyncio.to_thread(_core.open_by_key, sheet_id)


async def aget_worksheet(sheet_id: str, name: str):
    """Async: get worksheet handle by (sheet_id, tab name) using core cache."""
    return await asyncio.to_thread(_core.get_worksheet, sheet_id, name)


async def afetch_records(sheet_id: str, worksheet: str) -> list[dict[str, Any]]:
    """Async: get_all_records() with core's caching and retry, off the loop."""
    return await asyncio.to_thread(_core.fetch_records, sheet_id, worksheet)


async def afetch_values(sheet_id: str, worksheet: str) -> list[list[Any]]:
    """Async: get_all_values() with core's caching and retry, off the loop."""
    return await asyncio.to_thread(_core.fetch_values, sheet_id, worksheet)


async def acall_with_backoff(
    func: Callable[P, T],
    *args: P.args,
    attempts: int | None = None,
    base_delay: float | None = None,
    factor: float | None = None,
    **kwargs: P.kwargs,
) -> T:
    """
    Async retry wrapper for write/update helpers. Callers pass a sync gspread
    function (e.g., ws.update) plus args/kwargs. We invoke it in a thread and
    back off with await asyncio.sleep between attempts.
    """
    return await _retry_with_backoff_async(
        func, *args, attempts=attempts, base_delay=base_delay, factor=factor, **kwargs
    )


__all__ = [
    "aopen_by_key",
    "aget_worksheet",
    "afetch_records",
    "afetch_values",
    "acall_with_backoff",
]
