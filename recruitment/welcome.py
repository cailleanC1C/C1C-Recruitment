"""Welcome command integration bridged from the legacy Matchmaker bot."""

from __future__ import annotations

from typing import Dict, Iterable

from discord.ext import commands

from sheets import recruitment as sheets_recruitment

from . import ensure_loaded


async def setup(bot: commands.Bot) -> None:
    legacy = await ensure_loaded(bot)
    welcome_cog = getattr(legacy, "welcome_cog", None)
    if welcome_cog is None:
        return

    def _rows() -> Iterable[Dict]:
        return sheets_recruitment.fetch_welcome_templates()

    welcome_cog.get_rows = _rows  # type: ignore[attr-defined]
    try:
        welcome_cog.bot = bot  # type: ignore[attr-defined]
    except Exception:
        pass
