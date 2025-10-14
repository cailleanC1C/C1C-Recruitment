# modules/coreops/cog.py
from __future__ import annotations
import os, sys, time
from typing import Optional

from discord.ext import commands

from config.runtime import (
    get_env_name, get_bot_name, get_command_prefix,
    get_keepalive_interval_sec, get_watchdog_check_sec,
    get_watchdog_stall_sec, get_watchdog_disconnect_grace_sec,
)
from shared import socket_heartbeat as hb
from shared.coreops_render import (
    build_digest_line, build_health_embed, build_env_embed,
)
from shared.coreops_rbac import is_staff_member
from shared.help import build_help_embed


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


class CoreOps(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="health")
    @staff_only()
    async def health(self, ctx: commands.Context):
        env = get_env_name()
        bot_name = get_bot_name()
        version = os.getenv("BOT_VERSION", "dev")
        uptime = _uptime_sec(self.bot)
        latency = _latency_sec(self.bot)
        last_age = await hb.age_seconds()
        keepalive = get_keepalive_interval_sec()
        watchdog_check = get_watchdog_check_sec()
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
            watchdog_check_sec=watchdog_check,
            stall_after_sec=stall,
            disconnect_grace_sec=dgrace,
        )
        await ctx.reply(embed=embed)

    @commands.command(name="digest")
    @staff_only()
    async def digest(self, ctx: commands.Context):
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
    async def env(self, ctx: commands.Context):
        embed = build_env_embed(
            bot_name=get_bot_name(),
            env=get_env_name(),
            version=os.getenv("BOT_VERSION", "dev"),
            cfg_meta=_config_meta_from_app(),
        )
        await ctx.reply(embed=embed)

    @commands.command(name="help")
    async def help_(self, ctx: commands.Context):
        e = build_help_embed(
            prefix=get_command_prefix(),
            is_staff=is_staff_member(ctx.author),
            bot_version=os.getenv("BOT_VERSION", "dev"),
        )
        await ctx.reply(embed=e)


async def setup(bot):
    await bot.add_cog(CoreOps(bot))
