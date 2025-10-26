"""Shared recruitment roster helpers used by member and recruiter panels."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from shared.sheets import async_facade as sheets
from shared.sheets import recruitment as sheet_recruitment
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
    *,
    header_map: dict[str, int] | None,
) -> tuple[RecruitmentClanRecord, dict[str, int] | None]:
    if isinstance(entry, RecruitmentClanRecord):
        if not entry.roster.strip():
            raise ValueError("blank roster cell")
        return entry, header_map

    try:
        mapping = header_map or sheet_recruitment.get_clan_header_map()
    except Exception:
        mapping = header_map or {}

    def _cell(idx: int | None) -> str:
        if idx is None or idx < 0:
            return ""
        if idx >= len(entry):
            return ""
        value = entry[idx]
        return "" if value is None else str(value)

    row = tuple("" if cell is None else str(cell) for cell in entry)
    roster_idx = mapping.get("roster", search_helpers.COL_E_SPOTS)
    roster_cell = _cell(roster_idx).strip()
    if not roster_cell:
        raise ValueError("blank roster cell")

    open_idx = mapping.get("open_spots", search_helpers.COL_E_SPOTS)
    inactives_idx = mapping.get("inactives", search_helpers.IDX_AG_INACTIVES)
    reserved_idx = mapping.get("reserved", 28)

    open_spots = parse_spots_num(_cell(open_idx))
    inactives = parse_inactives_num(_cell(inactives_idx))
    reserved = parse_spots_num(_cell(reserved_idx))

    record = RecruitmentClanRecord(
        row=row,
        open_spots=open_spots,
        inactives=inactives,
        reserved=reserved,
        roster=roster_cell,
    )
    return record, mapping


def normalize_records(
    records: Sequence[RecruitmentClanRecord | Sequence[str]],
) -> list[RecruitmentClanRecord]:
    normalized: list[RecruitmentClanRecord] = []
    header_map: dict[str, int] | None = None
    for entry in records or []:
        try:
            record, header_map = _ensure_record(entry, header_map=header_map)
            normalized.append(record)
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
