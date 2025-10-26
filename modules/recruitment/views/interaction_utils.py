from __future__ import annotations

import discord
from discord import InteractionResponded


async def defer_once(
    interaction: discord.Interaction, *, thinking: bool = True
) -> bool:
    """Defer ``interaction`` if it has not been acknowledged yet."""

    try:
        is_done = interaction.response.is_done()
    except Exception:
        is_done = True
    if is_done:
        return False
    try:
        await interaction.response.defer(thinking=thinking)
    except InteractionResponded:
        return False
    return True


__all__ = ["defer_once"]
