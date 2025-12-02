from __future__ import annotations

"""Daily report listing currently open Welcome and Move Request tickets."""

import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord

from modules.common.tickets import TicketThread, fetch_ticket_threads
from shared.config import get_report_recruiters_dest_id

log = logging.getLogger("c1c.recruitment.reporting.open_tickets")


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_lines(tickets: Sequence[TicketThread]) -> list[str]:
    if not tickets:
        return ["🔹 None right now ✨"]
    return [
        f"🔹 [{ticket.name}]({ticket.url}) {_format_timestamp(ticket.created_at)}"
        for ticket in tickets
    ]


def _group_tickets(tickets: Iterable[TicketThread]) -> tuple[list[TicketThread], list[TicketThread]]:
    welcome: list[TicketThread] = []
    move_requests: list[TicketThread] = []
    for ticket in tickets:
        if not ticket.is_open:
            continue
        target = welcome if ticket.kind == "welcome" else move_requests
        target.append(ticket)
    welcome.sort(key=lambda item: item.created_at)
    move_requests.sort(key=lambda item: item.created_at)
    return welcome, move_requests


def _render_report(welcome: Sequence[TicketThread], move_requests: Sequence[TicketThread]) -> str:
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "Currently Open Tickets",
        "",
        "Welcome",
        *(_format_lines(welcome)),
        "",
        "Move Requests",
        *(_format_lines(move_requests)),
        "",
        f"last updated {now_text} •",
    ]
    return "\n".join(lines)


async def send_currently_open_tickets_report(bot: discord.Client) -> tuple[bool, str]:
    dest_id = get_report_recruiters_dest_id()
    if not dest_id:
        return False, "dest-missing"

    await bot.wait_until_ready()

    channel = bot.get_channel(dest_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(dest_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            log.warning("open tickets destination lookup failed", exc_info=True)
            return False, f"dest:{type(exc).__name__}"

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "dest-invalid"

    try:
        tickets = await fetch_ticket_threads(bot, include_archived=False, with_members=False)
    except Exception as exc:
        log.warning("failed to collect open tickets", exc_info=True)
        return False, f"fetch:{type(exc).__name__}"

    welcome, move_requests = _group_tickets(tickets)
    content = _render_report(welcome, move_requests)

    try:
        await channel.send(content=content)
    except Exception as exc:
        log.warning("failed to send open tickets report", exc_info=True)
        return False, f"send:{type(exc).__name__}"

    return True, "-"


__all__ = ["send_currently_open_tickets_report"]
