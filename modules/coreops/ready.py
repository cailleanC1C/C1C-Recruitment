"""CoreOps ready event helpers."""

from __future__ import annotations

import logging

from discord.ext import commands

from modules.onboarding import watcher_promo, watcher_welcome
from modules.onboarding.ui import panels


log = logging.getLogger("modules.coreops.ready")


async def on_ready(bot: commands.Bot) -> None:
    """Run startup wiring that must execute after the bot is ready."""

    # Existing startup wiring …
    # Register onboarding persistent views *after* the bot is ready to avoid race conditions.
    panels.register_views(bot)

    # Ensure both onboarding watchers are wired
    await watcher_welcome.setup(bot)
    await watcher_promo.setup(bot)

    # Guard against bots without a .logger attribute; fall back to module logger.
    try:
        logger = getattr(bot, "logger", None)
        if logger is None:
            logger = log
        logger.info("on_ready: onboarding views registered (post-ready)")
    except Exception:
        # Never let logging break startup
        pass
