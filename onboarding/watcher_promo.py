"""Promotion-thread watcher imported from the legacy WelcomeCrew bot."""

from __future__ import annotations

import logging

from discord.ext import commands

from shared.config import (
    get_enable_promo_watcher,
    get_log_channel_id,
    get_welcome_enabled,
)

from . import ensure_loaded

log = logging.getLogger("c1c.onboarding.promo_watcher")


async def _announce_disabled(bot: commands.Bot, message: str) -> None:
    log_channel_id = get_log_channel_id()
    if not log_channel_id:
        log.info("promo watcher disabled: %s", message)
        return

    async def send_notice() -> None:
        try:
            await bot.wait_until_ready()
            channel = bot.get_channel(log_channel_id)
            if channel is None:
                channel = await bot.fetch_channel(log_channel_id)  # type: ignore[assignment]
            if channel is None:
                return
            await channel.send(message)
        except Exception:
            log.warning("failed to announce promo watcher toggle", exc_info=True)

    bot.loop.create_task(send_notice())


async def setup(bot: commands.Bot) -> None:
    if not get_welcome_enabled() or not get_enable_promo_watcher():
        await _announce_disabled(bot, "📴 Promo watcher disabled via config toggle.")
        return

    # TODO(phase3): wire watcher tasks once Sheets-backed flows land.
    await ensure_loaded(bot)
