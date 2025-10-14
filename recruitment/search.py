"""Prefix commands and panels imported from the legacy Matchmaker bot."""

from __future__ import annotations

from discord.ext import commands

from shared.coreops_rbac import is_lead, is_recruiter

from . import ensure_loaded


def recruiter_only(message: str = "Recruiter access only."):
    async def predicate(ctx: commands.Context) -> bool:
        if is_recruiter(ctx):
            return True
        try:
            await ctx.reply(message)
        except Exception:
            pass
        return False

    return commands.check(predicate)


def lead_only(message: str = "Lead access only."):
    async def predicate(ctx: commands.Context) -> bool:
        if is_lead(ctx):
            return True
        try:
            await ctx.reply(message)
        except Exception:
            pass
        return False

    return commands.check(predicate)


async def setup(bot: commands.Bot) -> None:
    # TODO(phase3): wire recruitment search commands once Sheets access lands.
    await ensure_loaded(bot)
