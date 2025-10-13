# shared/coreops_prefix.py
from __future__ import annotations
import discord

def prefix_hint(prefix: str) -> discord.Embed:
    e = discord.Embed(
        title="Try this command with the bot prefix",
        description=f"Use `!{prefix} <command>` (or mention the bot).",
        colour=discord.Colour.orange(),
    )
    e.add_field(name="Examples", value=f"`!{prefix} health`\n`!{prefix} env`", inline=False)
    return e
