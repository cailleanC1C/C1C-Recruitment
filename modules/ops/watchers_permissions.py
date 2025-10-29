"""Watchers that keep the bot role overwrites in sync for new channels."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from modules.common import runtime as runtime_helpers
from shared.logfmt import channel_label
from .permissions_sync import BotPermissionManager

log = logging.getLogger(__name__)


class BotPermissionWatcher(commands.Cog):
    """Apply the configured permission profile to new or moved channels."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = BotPermissionManager.for_bot(bot)

    async def _apply_if_needed(
        self,
        channel: discord.abc.GuildChannel,
        *,
        reason: str,
    ) -> None:
        if getattr(channel, "guild", None) is None:
            return
        outcome, plan = await self.manager.apply_single(channel)
        if outcome == "applied":
            await runtime_helpers.send_log_message(
                "🔐 Bot permissions applied automatically: "
                f"{channel_label(channel.guild, getattr(channel, 'id', None))} — matched={plan.matched_by}"
            )
        elif outcome == "error":
            log.warning(
                "Watcher failed to update overwrites", extra={"channel": channel, "reason": reason}
            )
        elif outcome == "skip-manual":
            log.info(
                "Watcher respected manual deny for channel", extra={"channel": channel, "reason": reason}
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self, channel: discord.abc.GuildChannel
    ) -> None:
        await self._apply_if_needed(channel, reason="create")

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        before_category = getattr(before, "category_id", None)
        after_category = getattr(after, "category_id", None)
        if before_category == after_category:
            return
        await self._apply_if_needed(after, reason="category-change")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotPermissionWatcher(bot))
