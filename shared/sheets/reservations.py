"""Sheet adapter for clan seat reservations."""

from __future__ import annotations

import datetime as dt
import inspect
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Protocol, Sequence

from shared.sheets import async_core
from shared.sheets import recruitment

log = logging.getLogger(__name__)


class SupportsMemberLookup(Protocol):
    """Minimal protocol for Discord guild lookups."""

    def get_member(self, member_id: int) -> Any:
        ...


ResolveUserFn = Callable[[int], Awaitable[str | None] | str | None]


_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "thread_id": ("thread id", "thread", "ticket thread", "ticket thread id"),
    "ticket_user_id": ("ticket user id", "applicant id", "user id", "ticket_user_id"),
    "ticket_username": ("ticket username", "applicant", "applicant name", "username"),
    "recruiter_id": ("recruiter id", "staff id"),
    "clan_tag": ("clan tag", "tag"),
    "reserved_until": (
        "reserved until",
        "hold until",
        "expires",
        "reserved_until",
        "reservation expires",
    ),
    "created_at": ("created at", "created", "timestamp", "created_at"),
    "status": ("status",),
    "notes": ("notes", "note", "comment"),
}


@dataclass(slots=True)
class ReservationRow:
    """Normalized representation of a reservation ledger row."""

    row_number: int
    thread_id: str
    ticket_user_id: Optional[int]
    recruiter_id: Optional[int]
    clan_tag: str
    reserved_until: Optional[dt.date]
    created_at: Optional[dt.datetime]
    status: str
    notes: str
    ticket_username: Optional[str]
    raw: Sequence[str]

    @property
    def normalized_clan_tag(self) -> str:
        return _normalize_tag(self.clan_tag)

    @property
    def is_active(self) -> bool:
        return _normalize_status(self.status) == "active"


async def append_reservation_row(row_values: Sequence[Any]) -> None:
    """Append ``row_values`` to the reservations worksheet."""

    recruitment.ensure_service_account_credentials()
    sheet_id = recruitment.get_recruitment_sheet_id()
    tab_name = recruitment.get_reservations_tab_name()
    worksheet = await async_core.aget_worksheet(sheet_id, tab_name)
    payload = [str(value) if value is not None else "" for value in row_values]
    await async_core.acall_with_backoff(
        worksheet.append_row,
        payload,
        value_input_option="RAW",
    )


async def get_active_reservations_for_clan(clan_tag: str) -> List[ReservationRow]:
    """Return active reservations matching ``clan_tag``."""

    normalized = _normalize_tag(clan_tag)
    if not normalized:
        return []

    rows = await _load_reservations()
    return [row for row in rows if row.is_active and row.normalized_clan_tag == normalized]


async def count_active_reservations_for_clan(clan_tag: str) -> int:
    """Return the number of active reservations for ``clan_tag``."""

    reservations = await get_active_reservations_for_clan(clan_tag)
    return len(reservations)


async def get_active_reservations_by_clan() -> dict[str, List[ReservationRow]]:
    """Return a mapping of clan tag → active reservation rows."""

    rows = await _load_reservations()
    grouped: dict[str, List[ReservationRow]] = {}
    for row in rows:
        if not row.is_active:
            continue
        tag = row.normalized_clan_tag
        if not tag:
            continue
        grouped.setdefault(tag, []).append(row)
    return grouped


async def get_active_reservation_names_for_clan(
    clan_tag: str,
    guild: SupportsMemberLookup | None = None,
    *,
    resolver: ResolveUserFn | None = None,
) -> List[str]:
    """Resolve a friendly list of names for active reservations."""

    reservations = await get_active_reservations_for_clan(clan_tag)
    return await resolve_reservation_names(reservations, guild=guild, resolver=resolver)


async def resolve_reservation_names(
    reservations: Sequence[ReservationRow],
    *,
    guild: SupportsMemberLookup | None = None,
    resolver: ResolveUserFn | None = None,
) -> List[str]:
    """Resolve reservation holders to display names using the provided context."""

    names: List[str] = []
    seen: set[str] = set()
    for row in reservations:
        candidate = await _resolve_reservation_name(row, guild=guild, resolver=resolver)
        if not candidate:
            continue
        display = candidate.strip()
        if not display or display in seen:
            continue
        seen.add(display)
        names.append(display)
    return names


async def _resolve_reservation_name(
    row: ReservationRow,
    *,
    guild: SupportsMemberLookup | None,
    resolver: ResolveUserFn | None,
) -> str | None:
    if resolver and row.ticket_user_id is not None:
        try:
            resolved = resolver(row.ticket_user_id)
        except Exception:  # pragma: no cover - defensive guard around callbacks
            log.exception("reservation resolver callback raised", extra={"clan": row.clan_tag})
        else:
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved:
                text = str(resolved).strip()
                if text:
                    return text
    if guild and row.ticket_user_id is not None:
        try:
            member = guild.get_member(row.ticket_user_id)
        except Exception:  # pragma: no cover - guild lookup errors should not break flow
            log.exception(
                "guild member lookup failed",
                extra={"clan": row.clan_tag, "ticket_user_id": row.ticket_user_id},
            )
        else:
            if member is not None:
                for attr in ("display_name", "nick", "name"):
                    value = getattr(member, attr, None)
                    if value:
                        text = str(value).strip()
                        if text:
                            return text
    if row.ticket_username:
        text = row.ticket_username.strip()
        if text:
            return text
    if row.ticket_user_id is not None:
        return str(row.ticket_user_id)
    if row.thread_id:
        return row.thread_id
    return None


async def _load_reservations() -> List[ReservationRow]:
    matrix = await _fetch_reservations_matrix()
    if not matrix:
        return []

    header = matrix[0]
    records: List[ReservationRow] = []
    for offset, raw in enumerate(matrix[1:], start=2):
        if not _row_has_content(raw):
            continue
        record = ReservationRow(
            row_number=offset,
            **_parse_reservation_row(header, raw),
            raw=list(raw),
        )
        records.append(record)
    return records


async def _fetch_reservations_matrix() -> List[List[str]]:
    recruitment.ensure_service_account_credentials()
    sheet_id = recruitment.get_recruitment_sheet_id()
    tab_name = recruitment.get_reservations_tab_name()
    return await async_core.afetch_values(sheet_id, tab_name)


def _parse_reservation_row(header: Sequence[Any], row: Sequence[Any]) -> dict[str, Any]:
    index = _build_header_index(header)
    return {
        "thread_id": _cell_text(row, index.get("thread_id")),
        "ticket_user_id": _parse_int(_cell_text(row, index.get("ticket_user_id"))),
        "recruiter_id": _parse_int(_cell_text(row, index.get("recruiter_id"))),
        "clan_tag": _cell_text(row, index.get("clan_tag")),
        "reserved_until": _parse_date(_cell_text(row, index.get("reserved_until"))),
        "created_at": _parse_datetime(_cell_text(row, index.get("created_at"))),
        "status": _cell_text(row, index.get("status")),
        "notes": _cell_text(row, index.get("notes")),
        "ticket_username": _cell_text(row, index.get("ticket_username")) or None,
    }


def _build_header_index(header_row: Sequence[Any]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        key = _normalize_header(cell)
        if key and key not in lookup:
            lookup[key] = idx
    resolved: dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            candidate = lookup.get(alias)
            if candidate is not None:
                resolved[field] = candidate
                break
    return resolved


def _normalize_header(value: Any) -> str:
    text = "" if value is None else str(value).strip().lower()
    return " ".join(text.split())


def _normalize_tag(tag: str | None) -> str:
    text = "" if tag is None else str(tag).strip().upper()
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def _cell_text(row: Sequence[Any], index: Optional[int]) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    value = row[index]
    return "" if value is None else str(value).strip()


def _parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"-?\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _parse_date(value: str) -> Optional[dt.date]:
    text = value.strip()
    if not text:
        return None
    text = text.replace("Z", "")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def _parse_datetime(value: str) -> Optional[dt.datetime]:
    text = value.strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ):
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _row_has_content(row: Sequence[Any]) -> bool:
    return any(str(cell or "").strip() for cell in row)


__all__ = [
    "ReservationRow",
    "SupportsMemberLookup",
    "ResolveUserFn",
    "append_reservation_row",
    "get_active_reservations_for_clan",
    "count_active_reservations_for_clan",
    "get_active_reservations_by_clan",
    "get_active_reservation_names_for_clan",
    "resolve_reservation_names",
]
