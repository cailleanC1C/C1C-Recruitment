from __future__ import annotations

"""Helpers for working with ticket threads in welcome/promo channels."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord
from discord.ext import commands

from shared.config import get_promo_channel_id, get_welcome_channel_id

log = logging.getLogger("c1c.common.tickets")

_TICKET_CODE_RE = re.compile(r"\b([WRML])(\d{4})\b", re.IGNORECASE)


@dataclass(slots=True)
class TicketThread:
    """Normalized metadata for a ticket thread."""

    thread: discord.Thread
    code: str
    kind: str
    is_open: bool
    created_at: datetime
    member_ids: tuple[int, ...]

    @property
    def name(self) -> str:
        return getattr(self.thread, "name", self.code)

    @property
    def url(self) -> str:
        guild_id = getattr(getattr(self.thread, "guild", None), "id", 0) or 0
        return f"https://discord.com/channels/{guild_id}/{getattr(self.thread, 'id', 0)}"


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_ticket_code(name: str) -> str | None:
    """Extract the first ticket code (W|R|M|L####) from a thread name."""

    match = _TICKET_CODE_RE.search(name or "")
    if not match:
        return None
    prefix, suffix = match.groups()
    return f"{prefix.upper()}{suffix}"


def ticket_kind(code: str) -> str:
    """Return ``welcome`` for W#### codes, otherwise ``move``."""

    return "welcome" if str(code).upper().startswith("W") else "move"


def _is_closed(thread: discord.Thread) -> bool:
    name = (getattr(thread, "name", "") or "").lower()
    return getattr(thread, "archived", False) or name.startswith("closed-")


async def _list_archived(
    channel: discord.TextChannel, *, private: bool
) -> list[discord.Thread]:
    try:
        return [
            thread
            async for thread in channel.archived_threads(limit=None, private=private)
        ]
    except discord.Forbidden:
        log.debug(
            "archived thread fetch forbidden",
            extra={"channel_id": getattr(channel, "id", None), "private": private},
        )
    except discord.HTTPException as exc:
        log.debug(
            "archived thread fetch failed",
            exc_info=True,
            extra={
                "channel_id": getattr(channel, "id", None),
                "private": private,
                "error": str(exc),
            },
        )
    return []


async def _collect_threads(channel: discord.TextChannel, *, include_archived: bool) -> list[discord.Thread]:
    threads = list(getattr(channel, "threads", []) or [])
    if include_archived:
        threads.extend(await _list_archived(channel, private=False))
        threads.extend(await _list_archived(channel, private=True))
    return threads


async def fetch_ticket_threads(
    bot: commands.Bot,
    *,
    include_archived: bool = False,
    with_members: bool = False,
    guild_id: int | None = None,
) -> list[TicketThread]:
    """
    Collect ticket threads from configured welcome/promo channels.

    Threads are filtered by naming convention (W|R|M|L####). Returned objects
    include membership when ``with_members`` is True.
    """

    channel_ids = {
        cid for cid in (get_welcome_channel_id(), get_promo_channel_id()) if cid
    }
    threads: dict[int, discord.Thread] = {}

    for channel_id in channel_ids:
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        if not isinstance(channel, discord.TextChannel):
            continue
        if guild_id is not None and getattr(channel.guild, "id", None) != guild_id:
            continue
        for thread in await _collect_threads(channel, include_archived=include_archived):
            threads[getattr(thread, "id", 0)] = thread

    results: list[TicketThread] = []
    for thread in threads.values():
        code = parse_ticket_code(getattr(thread, "name", ""))
        if not code:
            continue
        is_open = not _is_closed(thread)

        members: tuple[int, ...] = ()
        if with_members:
            try:
                member_objs = await thread.fetch_members()
            except discord.Forbidden:
                member_objs = []
            except discord.HTTPException:
                member_objs = []
            members = tuple(
                getattr(member, "id")
                for member in member_objs
                if getattr(member, "id", None) is not None
            )

        results.append(
            TicketThread(
                thread=thread,
                code=code,
                kind=ticket_kind(code),
                is_open=is_open,
                created_at=_normalize_datetime(getattr(thread, "created_at", None)),
                member_ids=members,
            )
        )

    return results


__all__ = [
    "TicketThread",
    "fetch_ticket_threads",
    "parse_ticket_code",
    "ticket_kind",
]
