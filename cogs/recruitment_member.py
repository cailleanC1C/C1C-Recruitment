"""Placeholder cog for the member-facing recruitment panel (`!clansearch`).

This module intentionally registers no commands. The upcoming implementation will
load the cog when the `member_panel` flag in the Features sheet evaluates to
TRUE."""

from __future__ import annotations

from discord.ext import commands


class RecruitmentMember(commands.Cog):
    """Reserved hook for the clan search member panel."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(_bot: commands.Bot) -> None:
    """Placeholder setup awaiting `member_panel` feature flag enablement."""

    return None
