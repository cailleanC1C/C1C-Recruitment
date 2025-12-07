from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from shared.sheets import core
from shared.sheets import onboarding

log = logging.getLogger(__name__)

_HEADERS: Sequence[str] = ("ticket_number", "username")


def _normalize_ticket_number(ticket_number: str) -> str:
    return onboarding._fmt_ticket(ticket_number)


def _normalize_username(username: str) -> str:
    return (username or "").strip()


def _update_or_create(ticket_number: str, username: str) -> None:
    sheet_id, tab = onboarding._resolve_onboarding_and_welcome_tab()
    worksheet = core.get_worksheet(sheet_id, tab)
    header = onboarding._ensure_headers(worksheet, _HEADERS)

    ticket_idx = onboarding._column_index(header, "ticket_number")
    username_idx = onboarding._column_index(header, "username")
    normalized_ticket = _normalize_ticket_number(ticket_number)
    normalized_username = _normalize_username(username)

    rows = core.call_with_backoff(worksheet.get_all_values)
    target_row = None
    for row_number, row in enumerate(rows[1:], start=2):
        current = row[ticket_idx] if ticket_idx < len(row) else ""
        if _normalize_ticket_number(current) == normalized_ticket:
            target_row = row_number
            break

    if target_row is not None:
        updates = []
        if ticket_idx >= 0:
            ticket_col = onboarding._col_to_a1(ticket_idx)
            updates.append(
                {"range": f"{ticket_col}{target_row}", "values": [[normalized_ticket]]}
            )
        if username_idx >= 0:
            username_col = onboarding._col_to_a1(username_idx)
            updates.append(
                {"range": f"{username_col}{target_row}", "values": [[normalized_username]]}
            )
        if updates:
            core.call_with_backoff(worksheet.batch_update, updates)
            log.info(
                "🧾 welcome_ticket updated • ticket=%s • username=%s",
                normalized_ticket,
                normalized_username,
            )
        return

    row = ["" for _ in header]
    if ticket_idx >= 0:
        row[ticket_idx] = normalized_ticket
    if username_idx >= 0:
        row[username_idx] = normalized_username
    core.call_with_backoff(worksheet.append_row, row)
    log.info(
        "🧾 welcome_ticket inserted • ticket=%s • username=%s",
        normalized_ticket,
        normalized_username,
    )


async def save(ticket_number: str, username: str) -> None:
    await asyncio.to_thread(_update_or_create, ticket_number, username)
