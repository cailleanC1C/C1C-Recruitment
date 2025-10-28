"""Async welcome-thread watcher that logs closures to Sheets."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any, Optional

import discord
from discord.ext import commands

from modules.common import feature_flags
from modules.common import runtime as rt
from shared.config import get_welcome_channel_id
from shared.sheets.async_core import acall_with_backoff, aget_worksheet
from shared.sheets.onboarding import _resolve_onboarding_and_welcome_tab

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
    log_prefix: str

    def __init__(
        self,
        bot: commands.Bot,
        *,
        channel_id: int,
    ) -> None:
        self.bot = bot
        self.channel_id = channel_id
        self._sheet_tab: tuple[str, str] | None = None
        self._worksheet: Optional[Any] = None

    def _resolve_sheet_tab(self) -> tuple[str, str]:
        raise NotImplementedError

    async def _ensure_sheet_tab(self) -> tuple[str, str] | None:
        if self._sheet_tab is None:
            try:
                self._sheet_tab = self._resolve_sheet_tab()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await _send_runtime(
                    f"[{self.log_prefix}] degraded: cannot resolve tab (will retry on next event): {exc}"
                )
                return None
        return self._sheet_tab

    async def _worksheet_handle(self):
        sheet_tab = await self._ensure_sheet_tab()
        if sheet_tab is None:
            return None
        sheet_id, tab_name = sheet_tab
        if self._worksheet is None:
            self._worksheet = await aget_worksheet(sheet_id, tab_name)
        return self._worksheet

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        if after.parent_id != self.channel_id:
            return
        if not _transitioned_to_closed(before, after):
            return
        await self._record_closure(after)

    async def _record_closure(self, thread: discord.Thread) -> None:
        # TODO Phase 7 PR #3: call start_welcome_dialog when closure detected.
        timestamp = dt.datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        owner_name = _thread_owner_name(thread)
        row = [timestamp, str(thread.id), thread.name or "", owner_name]
        try:
            worksheet = await self._worksheet_handle()
            if worksheet is None:
                return
            await acall_with_backoff(
                worksheet.append_row,
                row,
                value_input_option="RAW",
            )
            await _send_runtime(
                f"[{self.log_prefix}] thread={thread.id} name={thread.name!r} owner={owner_name}"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception(
                "%s watcher failed to log closure", self.log_prefix, extra={"thread_id": thread.id}
            )
            await _send_runtime(
                f"[{self.log_prefix}] error logging thread={thread.id} name={thread.name!r}: {exc}"
            )
            self._worksheet = None


class WelcomeWatcher(_ThreadClosureWatcher):
    log_prefix = "welcome_watcher"

    def _resolve_sheet_tab(self) -> tuple[str, str]:
        return _resolve_onboarding_and_welcome_tab()


async def setup(bot: commands.Bot) -> None:
    if not feature_flags.is_enabled("welcome_dialog"):
        _announce(
            bot,
            "📴 Welcome watcher disabled: FeatureToggles['welcome_dialog'] is OFF.",
        )
        return
    if not feature_flags.is_enabled("welcome_enabled"):
        _announce(
            bot,
            "📴 Welcome watcher disabled: FeatureToggles['welcome_enabled'] is OFF.",
        )
        return
    if not feature_flags.is_enabled("enable_welcome_hook"):
        _announce(
            bot,
            "📴 Welcome watcher disabled: FeatureToggles['enable_welcome_hook'] is OFF.",
        )
        return

    channel_id = get_welcome_channel_id()
    if not channel_id:
        _announce(bot, "⚠️ Welcome watcher disabled: WELCOME_CHANNEL_ID missing.")
        return

    await bot.add_cog(WelcomeWatcher(bot, channel_id=channel_id))
    log.info(
        "welcome watcher enabled",
        extra={"channel_id": channel_id},
    )
