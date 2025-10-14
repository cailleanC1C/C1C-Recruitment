"""Welcome-thread watcher imported from the legacy WelcomeCrew bot."""

from __future__ import annotations

from discord.ext import commands

from . import ensure_loaded


async def setup(bot: commands.Bot) -> None:
    await ensure_loaded(bot)
