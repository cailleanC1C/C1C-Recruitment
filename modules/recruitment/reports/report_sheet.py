"""Async report helpers backed by the Sheets facade."""

from __future__ import annotations

import logging
from typing import Any

from shared.sheets import async_facade as sheets

log = logging.getLogger("c1c.recruitment.reports.sheet")

_DEFAULT_RANGE = "A1:D10"


async def generate_report(sheet_id: str, a1_range: str = _DEFAULT_RANGE) -> Any:
    """Fetch a matrix from Sheets using the async facade."""

    data = await sheets.sheets_read(sheet_id, a1_range)
    log.debug(
        "loaded report range",
        extra={"sheet_id": sheet_id, "range": a1_range, "rows": len(data or []) if isinstance(data, list) else None},
    )
    return data


__all__ = ["generate_report"]
