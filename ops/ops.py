"""Operational utilities commands."""

from __future__ import annotations

from discord.ext import commands

from shared.config import (
    get_env_name,
    get_allowed_guild_ids,
    get_sheet_tab_names,
    get_google_sheet_id,
    redact_ids,
)
from shared.coreops_rbac import is_staff_member


def staff_only():
    async def predicate(ctx: commands.Context):
        if is_staff_member(ctx.author):
            return True
        try:
            await ctx.reply("Staff only")
        except Exception:
            pass
        return False

    return commands.check(predicate)


class Ops(commands.Cog):
    """Small collection of operational status commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="config")
    @staff_only()
    async def config_summary(self, ctx: commands.Context) -> None:
        env = get_env_name()
        allow = get_allowed_guild_ids()
        tabs = get_sheet_tab_names()
        tab_line = ", ".join(f"{label}={name}" for label, name in tabs.items() if name)
        if not tab_line:
            tab_line = "—"

        sheet_state = "set" if get_google_sheet_id() else "missing"

        lines = [
            f"env: `{env}`",
            f"allow-list: {len(allow)} ({redact_ids(sorted(allow))})",
            f"connected guilds: {len(self.bot.guilds)}",
            f"tabs: {tab_line}",
            f"sheet id: {sheet_state}",
        ]

        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ops(bot))
