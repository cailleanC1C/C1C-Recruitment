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

from .coreops_rbac import is_admin, is_staff
from .sheets import cache_service

UTC = dt.timezone.utc
_CACHE = cache_service.cache

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
    asyncio.create_task(_CACHE._refresh(bucket, trigger=trigger, actor=actor))


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

    @commands.group(name="refresh", invoke_without_command=True)
    @is_admin()
    async def refresh_all(self, ctx: commands.Context):
        """Admin: Refresh all registered Sheets caches immediately."""
        buckets = list(_CACHE._buckets.keys())
        if not buckets:
            await ctx.send("⚠️ No cache buckets registered.")
            return
        await ctx.send(f"🧹 Refreshing: {', '.join(buckets)} (background).")
        for name in buckets:
            asyncio.create_task(_CACHE._refresh(name, trigger="manual", actor=str(ctx.author)))
        return

    @refresh_all.command(name="all")
    @is_admin()
    async def refresh_all_alias(self, ctx: commands.Context):
        """Alias for !refresh all (admin only)."""
        await self.refresh_all(ctx)

    @commands.command(name="rec_refresh_all")
    @is_admin()
    async def rec_refresh_all(self, ctx: commands.Context):
        """Admin: !rec refresh all alias"""
        await self.refresh_all(ctx)

    @commands.command(name="rec_refresh_clansinfo")
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

def setup(bot: commands.Bot):
    bot.add_cog(CoreOpsRefresh(bot))
