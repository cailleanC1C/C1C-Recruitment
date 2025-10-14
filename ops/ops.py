"""Operational utilities cog placeholder."""

from __future__ import annotations

from discord.ext import commands


class Ops(commands.Cog):
    """Empty cog reserved for future operational commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ops(bot))
