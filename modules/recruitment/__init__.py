"""Recruitment module package scaffolding."""

from __future__ import annotations

from discord.ext import commands


async def ensure_loaded(bot: commands.Bot) -> None:
    """Temporary loader shim retained for backward compatibility."""

    return None


__all__ = ["ensure_loaded"]
