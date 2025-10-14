"""Operational utilities commands."""

from __future__ import annotations

from discord.ext import commands

from shared.config import (
    get_env_name,
    get_allowed_guild_ids,
    get_onboarding_sheet_id,
    get_recruitment_sheet_id,
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
        recruitment_sheet = "set" if get_recruitment_sheet_id() else "missing"
        onboarding_sheet = "set" if get_onboarding_sheet_id() else "missing"

        lines = [
            f"env: `{env}`",
            f"allow-list: {len(allow)} ({redact_ids(sorted(allow))})",
            f"connected guilds: {len(self.bot.guilds)}",
            f"recruitment sheet: {recruitment_sheet}",
            f"onboarding sheet: {onboarding_sheet}",
        ]

        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ops(bot))
