"""CoreOps shared cog and RBAC helpers."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import time
from typing import Any, Optional

from discord.ext import commands

from config.runtime import (
    get_bot_name,
    get_command_prefix,
    get_env_name,
    get_watchdog_check_sec,
    get_watchdog_disconnect_grace_sec,
    get_watchdog_stall_sec,
)
from shared import socket_heartbeat as hb
from shared.config import (
    get_allowed_guild_ids,
    get_onboarding_sheet_id,
    get_recruitment_sheet_id,
    redact_ids,
)
from shared.coreops_render import (
    build_digest_line,
    build_env_embed,
    build_health_embed,
)
from shared.help import build_help_embed
from shared.sheets import cache_service

from .coreops_rbac import is_admin_member, is_staff_member

UTC = dt.timezone.utc


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


def staff_only() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if is_staff_member(getattr(ctx, "author", None)):
            return True
        try:
            await ctx.reply("Staff only")
        except Exception:
            pass
        return False

    return commands.check(predicate)


def _uptime_sec(bot: commands.Bot) -> float:
    started = getattr(bot, "_c1c_started_mono", None)
    return max(0.0, time.monotonic() - started) if started else 0.0


def _latency_sec(bot: commands.Bot) -> Optional[float]:
    try:
        return float(getattr(bot, "latency", None)) if bot.latency is not None else None
    except Exception:
        return None


def _config_meta_from_app() -> dict:
    # Try to read CONFIG_META from app; else fallback
    app = sys.modules.get("app")
    meta = getattr(app, "CONFIG_META", None) if app else None
    return meta or {"source": "runtime-only", "status": "ok", "loaded_at": None, "last_error": None}


class CoreOpsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="health")
    @staff_only()
    async def health(self, ctx: commands.Context) -> None:
        env = get_env_name()
        bot_name = get_bot_name()
        version = os.getenv("BOT_VERSION", "dev")
        uptime = _uptime_sec(self.bot)
        latency = _latency_sec(self.bot)
        last_age = await hb.age_seconds()
        keepalive = get_watchdog_check_sec()
        stall = get_watchdog_stall_sec()
        dgrace = get_watchdog_disconnect_grace_sec(stall)

        embed = build_health_embed(
            bot_name=bot_name,
            env=env,
            version=version,
            uptime_sec=uptime,
            latency_s=latency,
            last_event_age=last_age,
            keepalive_sec=keepalive,
            stall_after_sec=stall,
            disconnect_grace_sec=dgrace,
        )
        await ctx.reply(embed=embed)

    @commands.command(name="digest")
    @staff_only()
    async def digest(self, ctx: commands.Context) -> None:
        line = build_digest_line(
            bot_name=get_bot_name(),
            env=get_env_name(),
            uptime_sec=_uptime_sec(self.bot),
            latency_s=_latency_sec(self.bot),
            last_event_age=await hb.age_seconds(),
        )
        await ctx.reply(line)

    @commands.command(name="env")
    @staff_only()
    async def env(self, ctx: commands.Context) -> None:
        embed = build_env_embed(
            bot_name=get_bot_name(),
            env=get_env_name(),
            version=os.getenv("BOT_VERSION", "dev"),
            cfg_meta=_config_meta_from_app(),
        )
        await ctx.reply(embed=embed)

    @commands.command(name="help")
    async def help_(self, ctx: commands.Context) -> None:
        embed = build_help_embed(
            prefix=get_command_prefix(),
            is_staff=is_staff_member(ctx.author),
            bot_version=os.getenv("BOT_VERSION", "dev"),
        )
        await ctx.reply(embed=embed)

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

    @commands.group(name="refresh", invoke_without_command=True)
    @commands.guild_only()
    @commands.check_any(_admin_check(), _staff_check())
    async def refresh(self, ctx: commands.Context) -> None:
        """Admin/Staff group: manual cache refresh."""

        if not _admin_roles_configured():
            await ctx.send("⚠️ Admin roles not configured — refresh commands disabled.")
            return
        await ctx.send("Available: `!rec refresh all`, `!rec refresh clansinfo`")

    @refresh.command(name="all")
    @_admin_check()
    async def refresh_all(self, ctx: commands.Context) -> None:
        """Admin: clear & warm all registered Sheets caches."""

        caps = cache_service.capabilities()
        buckets = list(caps.keys())
        if not buckets:
            await ctx.send("⚠️ No cache buckets registered.")
            return
        await ctx.send(f"🧹 Refreshing: {', '.join(buckets)} (background).")
        for name in buckets:
            asyncio.create_task(cache_service.cache.refresh_now(name))

    @refresh.command(name="clansinfo")
    @_staff_check()
    async def refresh_clansinfo(self, ctx: commands.Context) -> None:
        """Staff/Admin: refresh 'clans' cache if age ≥ 60 min."""

        caps = cache_service.capabilities()
        clans = caps.get("clans")
        if not clans:
            await ctx.send("⚠️ No clansinfo cache registered.")
            return

        last_refresh = clans.get("last_refresh_at")
        now = dt.datetime.now(UTC)
        age_sec = 10**9
        if isinstance(last_refresh, dt.datetime):
            age_sec = int((now - last_refresh.astimezone(UTC)).total_seconds())

        if age_sec < 60 * 60:
            mins = age_sec // 60
            next_at = clans.get("next_refresh_at")
            nxt = ""
            if isinstance(next_at, dt.datetime):
                nxt = f" Next auto-refresh: {next_at.astimezone(UTC).strftime('%H:%M UTC')}"
            await ctx.send(f"✅ Clans cache fresh ({mins}m old).{nxt}")
            return

        await ctx.send("Refreshing clans (background).")
        asyncio.create_task(cache_service.cache.refresh_now("clans"))

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            qn = (ctx.command.qualified_name if getattr(ctx, "command", None) else "") or ""
            if qn.startswith("refresh all"):
                await ctx.send("⛔ You don't have permission to run admin refresh commands.")
                return
            if qn.startswith("refresh clansinfo"):
                await ctx.send("⛔ You need Staff (or Administrator) to run this.")
                return
        raise error


__all__ = [
    "UTC",
    "CoreOpsCog",
    "_admin_check",
    "_admin_roles_configured",
    "_staff_check",
]
