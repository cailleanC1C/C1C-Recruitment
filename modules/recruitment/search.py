"""Shared recruitment roster helpers used by member and recruiter panels."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from shared.sheets import async_facade as sheets
from shared.sheets.recruitment import RecruitmentClanRecord

from . import search_helpers
from .search_helpers import (
    parse_inactives_num,
    parse_spots_num,
    row_matches,
)

__all__ = [
    "fetch_roster_records",
    "filter_records",
    "normalize_records",
    "enforce_inactives_only",
]

log = logging.getLogger(__name__)


async def fetch_roster_records(*, force: bool = False) -> list[RecruitmentClanRecord]:
    """Load normalized clan roster records from Sheets."""

    records: Iterable[RecruitmentClanRecord] = await sheets.fetch_clan_records(
        force=force
    )
    return normalize_records(list(records))


def _ensure_record(
    entry: RecruitmentClanRecord | Sequence[str],
) -> RecruitmentClanRecord:
    if isinstance(entry, RecruitmentClanRecord):
        return entry

    row = tuple(str(cell or "") for cell in entry)
    roster_cell = (
        row[search_helpers.COL_E_SPOTS]
        if len(row) > search_helpers.COL_E_SPOTS
        else ""
    )
    open_spots = parse_spots_num(roster_cell)
    inactives = parse_inactives_num(
        row[search_helpers.IDX_AG_INACTIVES]
        if len(row) > search_helpers.IDX_AG_INACTIVES
        else ""
    )
    reserved = parse_spots_num(row[28] if len(row) > 28 else "")
    return RecruitmentClanRecord(
        row=row,
        open_spots=open_spots,
        inactives=inactives,
        reserved=reserved,
        roster=str(roster_cell).strip(),
    )


def normalize_records(
    records: Sequence[RecruitmentClanRecord | Sequence[str]],
) -> list[RecruitmentClanRecord]:
    normalized: list[RecruitmentClanRecord] = []
    for entry in records or []:
        try:
            normalized.append(_ensure_record(entry))
        except Exception:
            continue
    return normalized


def filter_records(
    records: Sequence[RecruitmentClanRecord | Sequence[str]],
    *,
    cb: str | None,
    hydra: str | None,
    chimera: str | None,
    cvc: str | None,
    siege: str | None,
    playstyle: str | None,
    roster_mode: str | None,
) -> list[RecruitmentClanRecord]:
    """Apply sheet and roster-mode filters to ``records``."""

    normalized = normalize_records(records)
    matches: list[RecruitmentClanRecord] = []
    if not normalized:
        return matches

    for record in normalized:
        try:
            if not row_matches(
                record.row,
                cb,
                hydra,
                chimera,
                cvc,
                siege,
                playstyle,
            ):
                continue
            if roster_mode == "open" and record.open_spots <= 0:
                continue
            if roster_mode == "full" and record.open_spots > 0:
                continue
            if roster_mode == "inactives" and record.inactives <= 0:
                continue
            matches.append(record)
        except Exception:
            continue

    return matches


def enforce_inactives_only(
    records: Sequence[RecruitmentClanRecord | Sequence[str]],
    roster_mode: str | None,
    *,
    context: str,
) -> list[RecruitmentClanRecord]:
    """Re-apply the inactives-only guard and emit a debug log when rows drop."""

    normalized = normalize_records(records)

    if roster_mode != "inactives":
        return normalized

    filtered = [record for record in normalized if record.inactives > 0]
    removed = len(normalized) - len(filtered)
    if removed:
        log.debug(
            "recruitment dropped rows failing inactives guard",
            extra={"removed": removed, "context": context},
        )
    return filtered
