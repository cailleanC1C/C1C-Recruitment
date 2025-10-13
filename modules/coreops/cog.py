# modules/coreops/cog.py
from __future__ import annotations
import os, sys, time
from typing import Optional

import discord
from discord.ext import commands

from config.runtime import (
    get_env_name, get_bot_name, get_command_prefix,
    get_keepalive_interval_sec, get_watchdog_stall_sec, get_watchdog_disconnect_grace_sec,
    get_admin_ids,
)
from shared import socket_heartbeat as hb
from shared.coreops_render import (
    build_digest_line, build_health_embed, build_env_embed,
)
from shared.coreops_prefix import prefix_hint


def _is_staff(user: discord.abc.User | discord.Member) -> bool:
    try:
        return int(user.id) in set(get_admin_ids())
    except Exception:
        return False


def staff_only():
    async def predicate(ctx: commands.Context):
        if _is_staff(ctx.author):
            return True
        # friendly hint for non-staff
        try:
            await ctx.reply(embed=prefix_hint(get_command_prefix()))
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
        # keep simple: point users to prefix usage; staff sees list via health/digest/env
        if _is_staff(ctx.author):
            await ctx.reply(f"`!{get_command_prefix()} health` · `digest` · `env` · `ping`")
        else:
            await ctx.reply(embed=prefix_hint(get_command_prefix()))


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreOps(bot))
