"""Onboarding bootstrap utilities."""

from __future__ import annotations

from discord.ext import commands

from modules.onboarding.welcome_flow import start_welcome_dialog

__all__ = ["ensure_loaded", "start_welcome_dialog"]


async def ensure_loaded(bot: commands.Bot) -> commands.Bot:
    """No-op placeholder to keep legacy call sites operational."""

    return bot
