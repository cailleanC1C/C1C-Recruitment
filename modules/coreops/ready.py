"""CoreOps ready event helpers."""

from __future__ import annotations

from discord.ext import commands


async def on_ready(bot: commands.Bot) -> None:
    """Run startup wiring that must execute after the bot is ready."""

    # Existing startup wiring …
    # Register onboarding persistent views *after* the bot is ready to avoid race conditions.
    from modules.onboarding.ui import panels

    panels.register_views(bot)
    bot.logger.info("on_ready: onboarding views registered (post-ready)")
