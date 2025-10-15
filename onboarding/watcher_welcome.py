"""Async welcome-thread watcher that logs closures to Sheets."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Optional

import discord
from discord.ext import commands

from shared import runtime as rt
from shared.config import (
    get_enable_welcome_watcher,
    get_onboarding_sheet_id,
    get_welcome_channel_id,
    get_welcome_enabled,
)
from shared.sheets.async_core import acall_with_backoff, aget_worksheet

UTC = dt.timezone.utc
log = logging.getLogger("c1c.onboarding.welcome_watcher")


def _transitioned_to_closed(before: discord.Thread, after: discord.Thread) -> bool:
    """Return ``True`` when the thread transitions into an archived/locked state."""

    before_archived = bool(getattr(before, "archived", False))
    after_archived = bool(getattr(after, "archived", False))
    before_locked = bool(getattr(before, "locked", False))
    after_locked = bool(getattr(after, "locked", False))

    reopened = (before_archived and not after_archived) or (
        before_locked and not after_locked
    )
    if reopened:
        return False
    just_archived = (not before_archived) and after_archived
    just_locked = (not before_locked) and after_locked
    return just_archived or just_locked


def _thread_owner_name(thread: discord.Thread) -> str:
    owner = thread.owner
    if owner is None and thread.guild is not None and thread.owner_id:
        owner = thread.guild.get_member(thread.owner_id)
    if owner is None:
        owner_id = getattr(thread, "owner_id", None)
        return str(owner_id or "unknown")
    display = getattr(owner, "display_name", None) or getattr(owner, "name", None)
    if display:
        return str(display)
    return str(getattr(owner, "id", "unknown"))


async def _send_runtime(message: str) -> None:
    try:
        await rt.send_log_message(message)
    except Exception:
        log.warning("failed to send welcome watcher log message", exc_info=True)


def _announce(bot: commands.Bot, message: str) -> None:
    log.info("welcome watcher notice: %s", message)

    async def runner() -> None:
        await _send_runtime(message)

    bot.loop.create_task(runner())


class _ThreadClosureWatcher(commands.Cog):
    tab_name: str
    log_prefix: str

    def __init__(self, bot: commands.Bot, *, sheet_id: str, channel_id: int) -> None:
        self.bot = bot
        self.sheet_id = sheet_id
        self.channel_id = channel_id
        self._worksheet: Optional[Any] = None

    async def _worksheet_handle(self):
        if self._worksheet is None:
            self._worksheet = await aget_worksheet(self.sheet_id, self.tab_name)
        return self._worksheet

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        if after.parent_id != self.channel_id:
            return
        if not _transitioned_to_closed(before, after):
            return
        await self._record_closure(after)

    async def _record_closure(self, thread: discord.Thread) -> None:
        timestamp = dt.datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        owner_name = _thread_owner_name(thread)
        row = [timestamp, str(thread.id), thread.name or "", owner_name]
        try:
            worksheet = await self._worksheet_handle()
            await acall_with_backoff(
                worksheet.append_row,
                row,
                value_input_option="RAW",
            )
            await _send_runtime(
                f"[{self.log_prefix}] thread={thread.id} name={thread.name!r} owner={owner_name}"
            )
        except Exception as exc:
            log.exception(
                "%s watcher failed to log closure", self.log_prefix, extra={"thread_id": thread.id}
            )
            await _send_runtime(
                f"[{self.log_prefix}] error logging thread={thread.id} name={thread.name!r}: {exc}"
            )
            self._worksheet = None


class WelcomeWatcher(_ThreadClosureWatcher):
    tab_name = "WelcomeTickets"
    log_prefix = "welcome_watcher"


async def setup(bot: commands.Bot) -> None:
    if not get_welcome_enabled():
        _announce(bot, "📴 Welcome watcher disabled: WELCOME_ENABLED is false.")
        return
    if not get_enable_welcome_watcher():
        _announce(bot, "📴 Welcome watcher disabled via config toggle.")
        return

    sheet_id = get_onboarding_sheet_id().strip()
    if not sheet_id:
        _announce(bot, "⚠️ Welcome watcher disabled: ONBOARDING_SHEET_ID missing.")
        return

    channel_id = get_welcome_channel_id()
    if not channel_id:
        _announce(bot, "⚠️ Welcome watcher disabled: WELCOME_CHANNEL_ID missing.")
        return

    await bot.add_cog(WelcomeWatcher(bot, sheet_id=sheet_id, channel_id=channel_id))
    log.info(
        "welcome watcher enabled",
        extra={"channel_id": channel_id, "tab": WelcomeWatcher.tab_name},
    )
