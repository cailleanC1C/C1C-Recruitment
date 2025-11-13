"""Helpers for recomputing clan availability based on reservations."""

from __future__ import annotations

import logging
import re
from typing import Sequence

from shared.sheets import async_core
from shared.sheets import recruitment
from shared.sheets import reservations

log = logging.getLogger(__name__)


async def recompute_clan_availability(
    clan_tag: str,
    *,
    guild: reservations.SupportsMemberLookup | None = None,
    resolver: reservations.ResolveUserFn | None = None,
) -> None:
    """Recompute AF/AH/AI for ``clan_tag`` and refresh the in-memory cache."""

    clan_entry = recruitment.find_clan_row(clan_tag)
    if clan_entry is None:
        raise ValueError(f"Unknown clan tag: {clan_tag}")

    sheet_row, row = clan_entry
    manual_open = _parse_manual_open_spots(row)

    active_reservations = await reservations.get_active_reservations_for_clan(clan_tag)
    reservation_count = len(active_reservations)
    available_after_reservations = max(manual_open - reservation_count, 0)

    names = await reservations.resolve_reservation_names(
        active_reservations,
        guild=guild,
        resolver=resolver,
    )
    reservation_summary = _format_reservation_summary(reservation_count, names)

    updated_row = list(row)
    _ensure_row_length(updated_row, 35)

    ag_value = updated_row[32] if len(updated_row) > 32 else ""
    updated_row[31] = str(available_after_reservations)
    updated_row[33] = str(reservation_count)
    updated_row[34] = reservation_summary

    sheet_id = recruitment.get_recruitment_sheet_id()
    tab_name = recruitment.get_clans_tab_name()
    worksheet = await async_core.aget_worksheet(sheet_id, tab_name)

    payload = [
        [
            available_after_reservations,
            ag_value,
            reservation_count,
            reservation_summary,
        ]
    ]
    await async_core.acall_with_backoff(
        worksheet.update,
        f"AF{sheet_row}:AI{sheet_row}",
        payload,
        value_input_option="RAW",
    )

    recruitment.update_cached_clan_row(sheet_row, updated_row)

    log.debug(
        "recomputed clan availability",
        extra={
            "clan_tag": _normalize_tag(clan_tag),
            "manual_open": manual_open,
            "active_reservations": reservation_count,
            "available_after_reservations": available_after_reservations,
        },
    )


def _parse_manual_open_spots(row: Sequence[str]) -> int:
    if len(row) <= 4:
        return 0
    return _to_int(row[4])


def _format_reservation_summary(count: int, names: Sequence[str]) -> str:
    if count <= 0:
        return ""
    if names:
        return f"{count} -> {', '.join(names)}"
    return f"{count} ->"


def _ensure_row_length(row: list[str], length: int) -> None:
    if len(row) >= length:
        return
    row.extend("" for _ in range(length - len(row)))


def _to_int(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"-?\d+", str(value))
    if not match:
        return 0
    try:
        return int(match.group(0))
    except ValueError:
        return 0


def _normalize_tag(tag: str | None) -> str:
    text = "" if tag is None else str(tag).strip().upper()
    return "".join(ch for ch in text if ch.isalnum())


__all__ = ["recompute_clan_availability"]
