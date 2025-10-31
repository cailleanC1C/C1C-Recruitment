"""Async adapter for Google Sheets operations."""

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
_DEFAULT_TIMEOUT = 15.0


def _get_executor() -> ThreadPoolExecutor:
    """Return the lazily initialised executor used for Sheets I/O."""

    global _EXECUTOR
    if _EXECUTOR is None:
        with _EXECUTOR_LOCK:
            if _EXECUTOR is None:
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=_MAX_WORKERS,
                    thread_name_prefix="sheets-io",
                )
                _logger.info("SheetsAsyncAdapter init (max_workers=4)")
    return _EXECUTOR


def shutdown_executor(wait: bool = True) -> None:
    """Shut down the shared executor if it has been initialised."""

    global _EXECUTOR
    if _EXECUTOR is None:
        return
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            return
        _EXECUTOR.shutdown(wait=wait)
        _EXECUTOR = None


async def _to_thread(
    func: Callable[P, T],
    *args: P.args,
    timeout: float | None = _DEFAULT_TIMEOUT,
    **kwargs: P.kwargs,
) -> T:
    """Execute ``func`` in the adapter executor and await the result."""

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_get_executor(), partial(func, *args, **kwargs))
    if timeout is None:
        return await future
    return await asyncio.wait_for(future, timeout)


# ---------
# Sync wrappers
# ---------

def open_spreadsheet(client: Any, key: str) -> Any:
    """Synchronously open a spreadsheet by ``key`` using ``client``."""

    return client.open_by_key(key)


def worksheet_by_title(workbook: Any, name: str) -> Any:
    """Return a worksheet from ``workbook`` by tab ``name``."""

    return workbook.worksheet(name)


def worksheet_by_index(workbook: Any, index: int) -> Any:
    """Return a worksheet from ``workbook`` by numeric ``index``."""

    return workbook.get_worksheet(index)


def worksheet_records_all(worksheet: Any) -> list[dict[str, Any]]:
    """Return all records from ``worksheet``."""

    return worksheet.get_all_records()


def worksheet_values_all(worksheet: Any) -> list[list[Any]]:
    """Return all cell values from ``worksheet``."""

    return worksheet.get_all_values()


def worksheet_values_get(worksheet: Any, a1_range: str) -> Any:
    """Return the values for ``a1_range`` from ``worksheet``."""

    return worksheet.get(a1_range)


def worksheet_values_update(worksheet: Any, a1_range: str, values: Any) -> Any:
    """Update ``worksheet`` values for ``a1_range``."""

    return worksheet.update(a1_range, values)


def batch_update(spreadsheet: Any, request_body: dict[str, Any]) -> Any:
    """Execute ``batch_update`` on ``spreadsheet``."""

    return spreadsheet.batch_update(request_body)


# ---------
# Async wrappers
# ---------

async def aopen_spreadsheet(
    client: Any, key: str, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> Any:
    """Async variant of :func:`open_spreadsheet`."""

    return await _to_thread(client.open_by_key, key, timeout=timeout)


async def aworksheet_by_title(
    workbook: Any, name: str, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> Any:
    """Async wrapper for :func:`worksheet_by_title`."""

    return await _to_thread(workbook.worksheet, name, timeout=timeout)


async def aworksheet_by_index(
    workbook: Any, index: int, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> Any:
    """Async wrapper for :func:`worksheet_by_index`."""

    return await _to_thread(workbook.get_worksheet, index, timeout=timeout)


async def aworksheet_records_all(
    worksheet: Any, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> list[dict[str, Any]]:
    """Async wrapper for :func:`worksheet_records_all`."""

    return await _to_thread(worksheet.get_all_records, timeout=timeout)


async def aworksheet_values_all(
    worksheet: Any, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> list[list[Any]]:
    """Async wrapper for :func:`worksheet_values_all`."""

    return await _to_thread(worksheet.get_all_values, timeout=timeout)


async def aworksheet_values_get(
    worksheet: Any, a1_range: str, *, timeout: float | None = _DEFAULT_TIMEOUT
) -> Any:
    """Async wrapper for :func:`worksheet_values_get`."""

    return await _to_thread(worksheet.get, a1_range, timeout=timeout)


async def aworksheet_values_update(
    worksheet: Any,
    a1_range: str,
    values: Any,
    *,
    timeout: float | None = _DEFAULT_TIMEOUT,
) -> Any:
    """Async wrapper for :func:`worksheet_values_update`."""

    return await _to_thread(worksheet.update, a1_range, values, timeout=timeout)


async def abatch_update(
    spreadsheet: Any,
    request_body: dict[str, Any],
    *,
    timeout: float | None = _DEFAULT_TIMEOUT,
) -> Any:
    """Async wrapper for :func:`batch_update`."""

    return await _to_thread(spreadsheet.batch_update, request_body, timeout=timeout)


async def arun(
    func: Callable[P, T],
    *args: P.args,
    timeout: float | None = _DEFAULT_TIMEOUT,
    **kwargs: P.kwargs,
) -> T:
    """Generic adapter helper for executing arbitrary callables asynchronously."""

    return await _to_thread(func, *args, timeout=timeout, **kwargs)


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
