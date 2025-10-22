"""Onboarding bootstrap utilities."""

from __future__ import annotations

from discord.ext import commands


async def ensure_loaded(bot: commands.Bot) -> commands.Bot:
    """No-op placeholder to keep legacy call sites operational."""
    return bot
