from __future__ import annotations

"""Daily report listing currently open Welcome and Move Request tickets."""

import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord
from discord import HTTPException

from modules.common.tickets import TicketThread, fetch_ticket_threads
from modules.recruitment.reporting.destinations import resolve_report_destination

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


def _chunk_lines(lines: Sequence[str], *, limit: int = 1024) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines or ("",):
        if len(line) > limit:
            line = f"{line[: limit - 1]}…"

        pending_len = len(line) + (1 if current else 0)
        if current and current_len + pending_len > limit:
            chunks.append("\n".join(current) or "\u200b")
            current = [line]
            current_len = len(line)
            continue

        current.append(line)
        current_len += pending_len

    if current:
        chunks.append("\n".join(current) or "\u200b")

    return chunks or ["\u200b"]


def _add_section(
    embed: discord.Embed, title: str, lines: Sequence[str]
) -> None:
    chunks = _chunk_lines(lines)
    for idx, chunk in enumerate(chunks):
        name = title if idx == 0 else f"{title} (cont.)"
        embed.add_field(name=name, value=chunk or "\u200b", inline=False)

        if len(embed) > 6000:
            embed.remove_field(-1)
            embed.add_field(
                name=f"{title} (truncated)",
                value="Additional tickets omitted due to length.",
                inline=False,
            )
            break


def _build_report_embed(
    welcome: Sequence[TicketThread], move_requests: Sequence[TicketThread]
) -> discord.Embed:
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title="Currently Open Tickets",
        description=f"Last updated {now_text}",
    )

    _add_section(embed, "Welcome", _format_lines(welcome))
    _add_section(embed, "Move Requests", _format_lines(move_requests))

    return embed


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


async def send_currently_open_tickets_report(bot: discord.Client) -> tuple[bool, str]:
    channel, error = await resolve_report_destination(bot)
    if channel is None:
        return False, error

    try:
        tickets = await fetch_ticket_threads(bot, include_archived=False, with_members=False)
    except Exception as exc:
        log.warning("failed to collect open tickets", exc_info=True)
        return False, f"fetch:{type(exc).__name__}"

    welcome, move_requests = _group_tickets(tickets)
    embed = _build_report_embed(welcome, move_requests)

    try:
        await channel.send(embeds=[embed])
    except HTTPException as exc:
        log.warning(
            "failed to send open tickets report (status=%s text=%r)",
            getattr(exc, "status", "?"),
            getattr(exc, "text", None),
            exc_info=True,
        )
        return False, f"send:{type(exc).__name__}"
    except Exception as exc:
        log.warning("failed to send open tickets report", exc_info=True)
        return False, f"send:{type(exc).__name__}"

    return True, "-"


__all__ = ["send_currently_open_tickets_report"]
