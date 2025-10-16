# modules/coreops/cog.py
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import time
from typing import Optional

from discord.ext import commands

from config.runtime import (
    get_env_name,
    get_bot_name,
    get_command_prefix,
    get_watchdog_check_sec,
    get_watchdog_stall_sec,
    get_watchdog_disconnect_grace_sec,
)
from shared import socket_heartbeat as hb
from shared.coreops_cog import (
    UTC,
    _admin_check,
    _admin_roles_configured,
    _staff_check,
)
from shared.coreops_render import (
    build_digest_line,
    build_env_embed,
    build_health_embed,
)
from shared.config import (
    get_allowed_guild_ids,
    get_onboarding_sheet_id,
    get_recruitment_sheet_id,
    redact_ids,
)
from shared.coreops_rbac import is_staff_member
from shared.help import build_help_embed
from shared.sheets import cache_service


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


class CoreOpsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _child_command_names(group: commands.Command) -> list[str]:
        if not group or not hasattr(group, "commands"):
            return []

        seen = set()
        names = []
        for sub in group.commands.values():
            name = getattr(sub, "name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return sorted(names)

    def _build_command_tree_lines(self) -> list[str]:
        top_level = sorted(
            {
                getattr(command, "name", "")
                for command in self.bot.commands
                if getattr(command, "name", None)
            }
        )

        lines = [
            f"top-level: {', '.join(top_level)}" if top_level else "top-level: (none)"
        ]

        refresh_map: dict[str, list[str]] = {}
        for command in self.bot.walk_commands():
            if getattr(command, "name", None) != "refresh":
                continue
            qualified = command.qualified_name or command.name
            if qualified in refresh_map:
                continue
            refresh_map[qualified] = self._child_command_names(command)

        for qualified in sorted(refresh_map):
            children = refresh_map[qualified]
            tail = ", ".join(children) if children else "-"
            lines.append(f"{qualified} -> [{tail}]")

        rec_group = self.bot.get_command("rec")
        if rec_group:
            rec_children = self._child_command_names(rec_group)
            tail = ", ".join(rec_children) if rec_children else "-"
            lines.append(f"rec -> [{tail}]")

            refresh_child = None
            if hasattr(rec_group, "commands"):
                for sub in rec_group.commands.values():
                    if getattr(sub, "name", None) == "refresh":
                        refresh_child = sub
                        break

            if refresh_child:
                refresh_children = self._child_command_names(refresh_child)
                tail = ", ".join(refresh_children) if refresh_children else "-"
                lines.append(f"rec refresh -> [{tail}]")

        return lines

    async def _send_command_tree(self, ctx: commands.Context) -> None:
        lines = self._build_command_tree_lines()
        text = "\n".join(lines) if lines else "(no commands)"
        await ctx.reply(f"```md\n{text}\n```")

    @commands.command(name="health")
    @staff_only()
    async def health(self, ctx: commands.Context):
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
    @commands.cooldown(1, 3, commands.BucketType.user)
    @_admin_check()
    async def refresh(self, ctx: commands.Context) -> None:
        """Admin group. Usage: !refresh all"""

        if not _admin_roles_configured():
            await ctx.send("⚠️ Admin roles not configured — admin refresh commands are disabled.")
            return
        if ctx.invoked_subcommand is None:
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
            asyncio.create_task(cache_service.cache.refresh_now(name))

    @commands.group(name="rec_refresh", invoke_without_command=True)
    async def rec_refresh(self, ctx: commands.Context) -> None:
        """Recruitment refresh commands."""

        if ctx.invoked_subcommand is None:
            await ctx.send("Try `!rec refresh all` or `!rec refresh clansinfo`.")

    @rec_refresh.command(name="all")
    @_admin_check()
    async def rec_refresh_all(self, ctx: commands.Context) -> None:
        """Alias: !rec refresh all (admin)."""

        await ctx.invoke(self.refresh_all)

    @rec_refresh.command(name="clansinfo")
    @_staff_check()
    async def rec_refresh_clansinfo(self, ctx: commands.Context) -> None:
        """Staff/Admin: refresh 'clans' cache if age >= 60 minutes."""

        caps = cache_service.capabilities()
        clans = caps.get("clans")
        if not clans:
            await ctx.send("⚠️ This bot has no clansinfo cache.")
            return

        last_refresh = clans.get("last_refresh_at")
        now = dt.datetime.now(UTC)
        age_sec = 10 ** 9
        if isinstance(last_refresh, dt.datetime):
            try:
                age_sec = int((now - last_refresh.astimezone(UTC)).total_seconds())
            except Exception:
                age_sec = int((now - last_refresh).total_seconds())

        if age_sec < 60 * 60:
            mins = age_sec // 60
            next_at = clans.get("next_refresh_at")
            tail = ""
            if isinstance(next_at, dt.datetime):
                try:
                    tail = f" Next auto-refresh at {next_at.astimezone(UTC).strftime('%H:%M UTC')}"
                except Exception:
                    tail = f" Next auto-refresh at {next_at.strftime('%H:%M UTC')}"
            await ctx.send(f"Clans cache is fresh (age: {mins}m).{tail}")
            return

        await ctx.send("Refreshing: clans (background).")
        asyncio.create_task(cache_service.cache.refresh_now("clans"))

    @commands.group(name="rec", invoke_without_command=True)
    async def rec(self, ctx: commands.Context) -> None:
        """Recruitment namespace."""

        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!rec help` for commands.")

    @rec.group(name="refresh", invoke_without_command=True)
    async def rec_refresh_alias(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `!rec refresh all` or `!rec refresh clansinfo`.")

    @rec_refresh_alias.command(name="all")
    @_admin_check()
    async def rec_refresh_alias_all(self, ctx: commands.Context) -> None:
        await ctx.invoke(self.rec_refresh_all)

    @rec_refresh_alias.command(name="clansinfo")
    @_staff_check()
    async def rec_refresh_alias_clansinfo(self, ctx: commands.Context) -> None:
        await ctx.invoke(self.rec_refresh_clansinfo)

    @rec.command(name="cmds", hidden=True)
    @_staff_check()
    async def rec_cmds(self, ctx: commands.Context) -> None:
        await self._send_command_tree(ctx)

    @rec.group(name="debug", invoke_without_command=True, hidden=True)
    @_staff_check()
    async def rec_debug(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await self._send_command_tree(ctx)

    @rec_debug.command(name="cmds", hidden=True)
    @_staff_check()
    async def rec_debug_cmds(self, ctx: commands.Context) -> None:
        await self._send_command_tree(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            qn = (ctx.command.qualified_name if getattr(ctx, "command", None) else "") or ""
            if qn.startswith("refresh") or qn.startswith("rec refresh all") or qn.startswith("rec_refresh all"):
                await ctx.send("⛔ You don't have permission to run admin refresh commands.")
                return
            if qn.startswith("rec refresh clansinfo") or qn.startswith("rec_refresh clansinfo"):
                await ctx.send("⛔ You need Staff (or Administrator) to run this.")
                return
        raise error


async def setup(bot):
    await bot.add_cog(CoreOpsCog(bot))
