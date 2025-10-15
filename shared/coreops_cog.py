"""CoreOps cog shim for shared refresh commands.

This module hosts the refresh commands that are shared across the recruitment
bot deployments.  The actual health/digest/env commands live in
``modules.coreops.cog``; this file only supplies the refresh helpers so they can
be mixed into the existing CoreOps cog implementation.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

from discord.ext import commands

from .coreops_rbac import is_admin_member, is_staff_member
from .sheets import cache_service

UTC = dt.timezone.utc
_CACHE = cache_service.cache


def _admin_roles_configured() -> bool:
    """Return True when admin roles are configured (defaults to True)."""

    try:
        from .coreops_rbac import admin_roles_configured  # type: ignore
    except Exception:
        return True
    try:
        return bool(admin_roles_configured())  # type: ignore[misc]
    except Exception:
        return True


def _admin_check() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if not _admin_roles_configured():
            # Let the command body display the explicit disabled message.
            return True
        return is_admin_member(getattr(ctx, "author", None))

    return commands.check(predicate)


def _staff_check() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        if is_staff_member(author) or is_admin_member(author):
            return True
        perms = getattr(getattr(author, "guild_permissions", None), "administrator", False)
        return bool(perms)

    return commands.check(predicate)


class CoreOpsCog(commands.Cog):
    """Provide refresh commands for the CoreOps namespace."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------- Refresh commands ---------------------------
    @commands.group(name="refresh", invoke_without_command=False)
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @_admin_check()
    async def refresh(self, ctx: commands.Context) -> None:
        """Admin group. Usage: !refresh all"""

        if not _admin_roles_configured():
            await ctx.send("⚠️ Admin roles not configured — admin refresh commands are disabled.")
            return
        await ctx.send("Try `!refresh all`.")

    @refresh.command(name="all")
    @_admin_check()
    async def refresh_all(self, ctx: commands.Context) -> None:
        """Admin: Clear & warm all registered Sheets caches."""

        if not _admin_roles_configured():
            await ctx.send("⚠️ Admin roles not configured — admin refresh commands are disabled.")
            return
        caps = cache_service.capabilities()
        buckets = list(caps.keys())
        if not buckets:
            await ctx.send("⚠️ No cache buckets registered.")
            return
        await ctx.send(f"🧹 Refreshing: {', '.join(buckets)} (background).")
        for name in buckets:
            asyncio.create_task(_CACHE.refresh_now(name))

    # Existing `rec` group already hosts ping/health/digest/env
    @commands.group(name="rec", invoke_without_command=True)
    async def rec(self, ctx: commands.Context) -> None:
        """Recruitment namespace."""

        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!rec help` for commands.")

    @rec.group(name="refresh", invoke_without_command=False)
    async def rec_refresh(self, ctx: commands.Context) -> None:
        """Recruitment refresh commands."""

        if ctx.invoked_subcommand is None:
            await ctx.send("Try `!rec refresh all` or `!rec refresh clansinfo`.")

    @rec_refresh.command(name="all")
    @_admin_check()
    async def rec_refresh_all(self, ctx: commands.Context) -> None:
        """Alias: !rec refresh all (admin)."""

        await self.refresh_all(ctx)

    @rec_refresh.command(name="clansinfo")
    @_staff_check()
    async def rec_refresh_clansinfo(self, ctx: commands.Context) -> None:
        """Staff/Admin: refresh 'clans' cache if age >= 60 minutes."""

        bucket = _CACHE.get_bucket("clans")
        if not bucket:
            await ctx.send("⚠️ This bot has no clansinfo cache.")
            return
        age = bucket.age_sec() or 10**9
        if age < 60 * 60:
            mins = age // 60
            next_at = bucket.next_refresh_at()
            tail = ""
            if isinstance(next_at, dt.datetime):
                try:
                    tail = f" Next auto-refresh at {next_at.astimezone(UTC).strftime('%H:%M UTC')}"
                except Exception:
                    tail = f" Next auto-refresh at {next_at.strftime('%H:%M UTC')}"
            await ctx.send(f"Clans cache is fresh (age: {mins}m).{tail}")
            return
        await ctx.send("Refreshing: clans (background).")
        asyncio.create_task(_CACHE.refresh_now("clans"))

    # Make RBAC denials visible for this cog (no silent failures)
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            qn = (ctx.command.qualified_name if getattr(ctx, "command", None) else "") or ""
            if qn.startswith("refresh") or qn.startswith("rec refresh all"):
                await ctx.send("⛔ You don't have permission to run admin refresh commands.")
                return
            if qn.startswith("rec refresh clansinfo"):
                await ctx.send("⛔ You need Staff (or Administrator) to run this.")
                return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoreOpsCog(bot))
