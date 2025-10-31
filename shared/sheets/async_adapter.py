"""Async adapter for Google Sheets operations.

This module centralises offloading of blocking gspread calls into a bounded
:class:`~concurrent.futures.ThreadPoolExecutor`. Both synchronous and
``async`` helpers route through the same entry points so callers can migrate
without duplicating wrapper logic.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Lock
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

_logger = logging.getLogger(__name__)
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = Lock()
_MAX_WORKERS = 4


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        with _EXECUTOR_LOCK:
            if _EXECUTOR is None:
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=_MAX_WORKERS,
                    thread_name_prefix="sheets-io",
                )
                _logger.info(
                    "SheetsAsyncAdapter initialized (max_workers=%d)", _MAX_WORKERS
                )
    return _EXECUTOR


def shutdown_executor(wait: bool = True) -> None:
    """Shut down the shared executor if it has been initialised."""

    global _EXECUTOR
    if _EXECUTOR is not None:
        with _EXECUTOR_LOCK:
            if _EXECUTOR is not None:
                _EXECUTOR.shutdown(wait=wait)
                _EXECUTOR = None
                _logger.info("SheetsAsyncAdapter executor shut down")


async def _run_async(
    func: Callable[P, T],
    *args: P.args,
    timeout: float | None = None,
    **kwargs: P.kwargs,
) -> T:
    """Execute ``func`` in the adapter executor and await the result."""

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(
        _get_executor(), partial(func, *args, **kwargs)
    )
    if timeout is not None:
        return await asyncio.wait_for(future, timeout)
    return await future


def _run_sync(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Execute ``func`` synchronously (for compatibility with sync callers)."""

    return func(*args, **kwargs)


# ---------
# Wrappers
# ---------

def open_spreadsheet(client: Any, key: str) -> Any:
    """Synchronously open a spreadsheet by ``key`` using ``client``."""

    return _run_sync(client.open_by_key, key)


async def aopen_spreadsheet(
    client: Any, key: str, *, timeout: float | None = None
) -> Any:
    """Async variant of :func:`open_spreadsheet`."""

    return await _run_async(client.open_by_key, key, timeout=timeout)


def worksheet_by_title(workbook: Any, name: str) -> Any:
    """Return a worksheet from ``workbook`` by tab ``name``."""

    return _run_sync(workbook.worksheet, name)


async def aworksheet_by_title(
    workbook: Any, name: str, *, timeout: float | None = None
) -> Any:
    """Async wrapper for :func:`worksheet_by_title`."""

    return await _run_async(workbook.worksheet, name, timeout=timeout)


def worksheet_by_index(workbook: Any, index: int) -> Any:
    """Return a worksheet from ``workbook`` by numeric ``index``."""

    return _run_sync(workbook.get_worksheet, index)


async def aworksheet_by_index(
    workbook: Any, index: int, *, timeout: float | None = None
) -> Any:
    """Async wrapper for :func:`worksheet_by_index`."""

    return await _run_async(workbook.get_worksheet, index, timeout=timeout)


def worksheet_records_all(worksheet: Any) -> list[dict[str, Any]]:
    """Return all records from ``worksheet``."""

    return _run_sync(worksheet.get_all_records)


async def aworksheet_records_all(
    worksheet: Any, *, timeout: float | None = None
) -> list[dict[str, Any]]:
    """Async wrapper for :func:`worksheet_records_all`."""

    return await _run_async(worksheet.get_all_records, timeout=timeout)


def worksheet_values_all(worksheet: Any) -> list[list[Any]]:
    """Return all cell values from ``worksheet``."""

    return _run_sync(worksheet.get_all_values)


async def aworksheet_values_all(
    worksheet: Any, *, timeout: float | None = None
) -> list[list[Any]]:
    """Async wrapper for :func:`worksheet_values_all`."""

    return await _run_async(worksheet.get_all_values, timeout=timeout)


def worksheet_values_get(worksheet: Any, a1_range: str) -> Any:
    """Return the values for ``a1_range`` from ``worksheet``."""

    return _run_sync(worksheet.get, a1_range)


async def aworksheet_values_get(
    worksheet: Any, a1_range: str, *, timeout: float | None = None
) -> Any:
    """Async wrapper for :func:`worksheet_values_get`."""

    return await _run_async(worksheet.get, a1_range, timeout=timeout)


def worksheet_values_update(worksheet: Any, a1_range: str, values: Any) -> Any:
    """Update ``worksheet`` values for ``a1_range``."""

    return _run_sync(worksheet.update, a1_range, values)


async def aworksheet_values_update(
    worksheet: Any,
    a1_range: str,
    values: Any,
    *,
    timeout: float | None = None,
) -> Any:
    """Async wrapper for :func:`worksheet_values_update`."""

    return await _run_async(worksheet.update, a1_range, values, timeout=timeout)


def batch_update(spreadsheet: Any, request_body: dict[str, Any]) -> Any:
    """Execute ``batch_update`` on ``spreadsheet``."""

    return _run_sync(spreadsheet.batch_update, request_body)


async def abatch_update(
    spreadsheet: Any, request_body: dict[str, Any], *, timeout: float | None = None
) -> Any:
    """Async wrapper for :func:`batch_update`."""

    return await _run_async(spreadsheet.batch_update, request_body, timeout=timeout)


async def arun(
    func: Callable[P, T],
    *args: P.args,
    timeout: float | None = None,
    **kwargs: P.kwargs,
) -> T:
    """Generic adapter helper for executing arbitrary callables asynchronously."""

    return await _run_async(func, *args, timeout=timeout, **kwargs)


__all__ = [
    "aopen_spreadsheet",
    "aworksheet_by_title",
    "aworksheet_by_index",
    "aworksheet_records_all",
    "aworksheet_values_all",
    "aworksheet_values_get",
    "aworksheet_values_update",
    "abatch_update",
    "arun",
    "batch_update",
    "open_spreadsheet",
    "shutdown_executor",
    "worksheet_by_index",
    "worksheet_by_title",
    "worksheet_records_all",
    "worksheet_values_all",
    "worksheet_values_get",
    "worksheet_values_update",
]
