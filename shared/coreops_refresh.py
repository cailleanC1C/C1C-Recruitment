from __future__ import annotations
"""
Shared CoreOps refresh commands for all bots using shared.sheets.cache_service.
- !refresh all  (Admin)
- !rec refresh all  (Admin alias)
- !rec refresh clansinfo  (Staff/Admin)
"""

import asyncio
import datetime as dt
from typing import Optional

import discord
from discord.ext import commands

from .coreops_rbac import is_admin_member, is_staff_member
from .sheets import cache_service

UTC = dt.timezone.utc
_CACHE = cache_service.cache

# --- configuration probe (non-invasive) --------------------------------------

def _admin_roles_configured() -> bool:
    """Check whether ADMIN_ROLE_IDS are configured, defaulting to True."""

    try:
        from .coreops_rbac import admin_roles_configured  # type: ignore
    except Exception:
        return True
    try:
        return bool(admin_roles_configured())  # type: ignore[func-returns-value]
    except Exception:
        return True

# --- RBAC decorator wrappers (use coreops_rbac helpers) ----------------------

def is_admin():
    return commands.check(lambda ctx: is_admin_member(getattr(ctx, "author", None)))

def is_staff():
    # Staff includes admins
    return commands.check(
        lambda ctx: is_staff_member(getattr(ctx, "author", None))
        or is_admin_member(getattr(ctx, "author", None))
    )

# --- helpers ---------------------------------------------------------

async def _refresh_bucket(ctx: commands.Context, bucket: str, actor: str, trigger: str) -> None:
    b = _CACHE.get_bucket(bucket)
    if not b:
        await ctx.send(f"⚠️ No such cache bucket: `{bucket}`")
        return
    # Debounce: skip if already refreshing
    if b.refreshing and not b.refreshing.done():
        age = int((dt.datetime.now(UTC) - (b.last_refresh or dt.datetime.now(UTC))).total_seconds())
        await ctx.send(f"🔄 `{bucket}` is already refreshing (started {age}s ago).")
        return
    await ctx.send(f"⏳ Refreshing `{bucket}` cache (background)...")
    asyncio.create_task(_CACHE.refresh_now(bucket, trigger=trigger, actor=actor))


def _fmt_age(b) -> str:
    age = b.age_sec()
    if age is None:
        return "—"
    mins = age // 60
    if mins < 60:
        return f"{mins}m"
    hrs = mins // 60
    return f"{hrs}h{mins%60:02d}m"


async def _too_soon(ctx: commands.Context, b, next_time: Optional[dt.datetime]) -> None:
    msg = f"🕐 Clans cache is fresh (age: {_fmt_age(b)})."
    if next_time:
        msg += f" Next auto-refresh at {next_time.strftime('%H:%M UTC')}."
    await ctx.send(msg)


# --- command registration --------------------------------------------

class CoreOpsRefresh(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Admin: !refresh all
    @commands.group(name="refresh", invoke_without_command=False)
    @is_admin()
    async def refresh(self, ctx: commands.Context):
        """Admin group. Usage: !refresh all"""
        if not _admin_roles_configured():
            await ctx.send(
                "⚠️ Admin roles not configured — admin refresh commands are disabled."
            )
            return

    @refresh.command(name="all")
    @is_admin()
    async def refresh_all(self, ctx: commands.Context):
        """Admin: Refresh all registered Sheets caches immediately."""
        if not _admin_roles_configured():
            await ctx.send(
                "⚠️ Admin roles not configured — admin refresh commands are disabled."
            )
            return
        caps = cache_service.capabilities()
        buckets = list(caps.keys())
        if not buckets:
            await ctx.send("⚠️ No cache buckets registered.")
            return
        await ctx.send(f"🧹 Refreshing: {', '.join(buckets)} (background).")
        for name in buckets:
            asyncio.create_task(_CACHE.refresh_now(name, actor=str(ctx.author), trigger="manual"))
        return

    # Admin alias: !rec refresh all
    @commands.group(name="rec", invoke_without_command=False)
    async def rec(self, ctx: commands.Context):
        """Recruitment namespace."""
        pass

    @rec.group(name="refresh", invoke_without_command=False)
    async def rec_refresh(self, ctx: commands.Context):
        """Recruitment refresh group."""
        pass

    @rec_refresh.command(name="all")
    @is_admin()
    async def rec_refresh_all(self, ctx: commands.Context):
        """Alias: !rec refresh all (admin)"""
        if not _admin_roles_configured():
            await ctx.send(
                "⚠️ Admin roles not configured — admin refresh commands are disabled."
            )
            return
        await self.refresh_all(ctx)

    # Staff: !rec refresh clansinfo  (60m guard)
    @rec_refresh.command(name="clansinfo")
    @is_staff()
    async def rec_refresh_clansinfo(self, ctx: commands.Context):
        """Staff: refresh bot_info cache if older than 60 minutes."""
        b = _CACHE.get_bucket("clans")
        if not b:
            await ctx.send("⚠️ This bot has no clansinfo cache.")
            return
        age = b.age_sec() or 999999
        if age < 60 * 60:
            await _too_soon(ctx, b, b.next_refresh_at())
            return
        await _refresh_bucket(ctx, "clans", str(ctx.author), "manual")

# --- setup ------------------------------------------------------------

async def setup(bot: commands.Bot):
    await bot.add_cog(CoreOpsRefresh(bot))
