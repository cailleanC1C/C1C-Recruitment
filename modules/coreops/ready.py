"""CoreOps ready event helpers."""

from __future__ import annotations

from discord.ext import commands


async def on_ready(bot: commands.Bot) -> None:
    """Run startup wiring that must execute after the bot is ready."""

    # Existing startup wiring …
    # Register onboarding persistent views *after* the bot is ready to avoid race conditions.
    from modules.onboarding.ui import panels

    panels.register_views(bot)

    # Guard against bots without a .logger attribute; fall back to module logger.
    try:
        logger = getattr(bot, "logger", None)
        if logger is None:
            import logging

            logger = logging.getLogger("modules.coreops.ready")
        logger.info("on_ready: onboarding views registered (post-ready)")
    except Exception:
        # Never let logging break startup
        pass
