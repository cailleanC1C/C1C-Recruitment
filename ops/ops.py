"""Operational utilities commands."""

from __future__ import annotations

from discord.ext import commands


class Ops(commands.Cog):
    """Small collection of operational status commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ops(bot))
