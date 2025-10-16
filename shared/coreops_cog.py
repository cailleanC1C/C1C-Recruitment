"""CoreOps shared cog and RBAC helpers."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import re
import sys
import time
from importlib import import_module
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import discord
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
    get_config_snapshot,
    get_onboarding_sheet_id,
    get_recruitment_sheet_id,
    redact_ids,
    redact_value,
)
from shared.coreops_render import (
    build_digest_line,
    build_health_embed,
)
from shared.help import build_help_embed
from shared.sheets import cache_service

from .coreops_rbac import (
    admin_only,
    can_manage_guild,
    guild_only_denied_msg,
    is_admin_member,
    is_staff_member,
    ops_only,
)

UTC = dt.timezone.utc

logger = logging.getLogger(__name__)

_NAME_CACHE_TTL_SEC = 600.0
_ID_PATTERN = re.compile(r"\d{5,}")
_ID_KEY_HINTS = ("ID", "ROLE", "CHANNEL", "THREAD", "GUILD")
_ENV_KEY_HINTS = (
    "SHEET",
    "SHEETS",
    "GSPREAD",
    "GOOGLE",
    "SERVICE",
    "RECRUIT",
    "ONBOARD",
    "WELCOME",
    "PROMO",
)
_SHEET_CONFIG_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("Recruitment", "sheets.recruitment"),
    ("Onboarding", "sheets.onboarding"),
)
_sheet_cache_errors_logged: Set[str] = set()


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
            await ctx.reply("Staff only.")
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


def _sheet_cache_snapshot(module_name: str) -> Dict[str, Any]:
    try:
        module = import_module(module_name)
    except Exception as exc:  # pragma: no cover - defensive logging
        if module_name not in _sheet_cache_errors_logged:
            _sheet_cache_errors_logged.add(module_name)
            logger.warning(
                "failed to import sheet config cache",
                extra={"module": module_name},
                exc_info=exc,
            )
        return {}

    cache = getattr(module, "_CONFIG_CACHE", None)
    if isinstance(cache, dict):
        return dict(cache)
    return {}


def _normalize_snapshot_value(value: object) -> object:
    if isinstance(value, set):
        try:
            return sorted(value)
        except TypeError:
            return list(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _clip(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if not clean:
        return "—"
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1]}…"


def _format_table(entries: Sequence[Tuple[str, str, str]]) -> str:
    if not entries:
        return "—"

    header = f"{'KEY':<28} {'VALUE':<32} RESOLVED"
    lines = [header, "-" * len(header)]
    for key, value, resolved in entries:
        key_text = _clip(key, 28).ljust(28)
        value_text = _clip(value, 32).ljust(32)
        resolved_text = _clip(resolved, 64)
        lines.append(f"{key_text} {value_text} {resolved_text}")

    return "```\n" + "\n".join(lines) + "\n```"


def _format_resolved(names: Sequence[str]) -> str:
    if not names:
        return "—"

    seen: List[str] = []
    for name in names:
        label = name or "(not found)"
        if label not in seen:
            seen.append(label)
    return ", ".join(seen) if seen else "—"


def _extract_ids(key: str, value: object) -> List[int]:
    key_upper = str(key).upper()
    if not any(hint in key_upper for hint in _ID_KEY_HINTS):
        return []

    result: List[int] = []
    seen: Set[int] = set()

    def _push(candidate: int) -> None:
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)

    def _walk(item: object) -> None:
        if item is None:
            return
        if isinstance(item, bool):
            return
        if isinstance(item, int):
            if item >= 0:
                _push(int(item))
            return
        if isinstance(item, float) and item.is_integer():
            _push(int(item))
            return
        if isinstance(item, str):
            for match in _ID_PATTERN.findall(item):
                try:
                    _push(int(match))
                except (TypeError, ValueError):
                    continue
            return
        if isinstance(item, dict):
            for sub in item.values():
                _walk(sub)
            return
        if isinstance(item, (list, tuple, set)):
            for sub in item:
                _walk(sub)

    _walk(value)
    return result


def _candidate_env_keys(snapshot: Dict[str, Any]) -> List[str]:
    keys = {str(k) for k in snapshot.keys()}
    for key in os.environ.keys():
        if key in keys:
            continue
        if not key.isupper():
            continue
        if any(hint in key for hint in _ENV_KEY_HINTS):
            keys.add(key)
    return sorted(keys)


def _describe_role(role: discord.Role) -> str:
    name = getattr(role, "name", "role")
    guild = getattr(role, "guild", None)
    guild_name = getattr(guild, "name", None)
    if guild_name:
        return f"@{name} · {guild_name}"
    return f"@{name}"


def _describe_channel(channel: discord.abc.GuildChannel | discord.Thread) -> str:
    name = getattr(channel, "name", "channel")
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        base = f"#{name}"
    elif isinstance(channel, discord.VoiceChannel):
        base = f"🔊 {name}"
    elif getattr(discord, "StageChannel", None) and isinstance(channel, discord.StageChannel):  # type: ignore[attr-defined]
        base = f"🎙️ {name}"
    elif isinstance(channel, discord.CategoryChannel):
        base = f"📂 {name}"
    else:
        base = str(name)
    guild = getattr(channel, "guild", None)
    guild_name = getattr(guild, "name", None)
    if guild_name:
        return f"{base} · {guild_name}"
    return base


class _IdResolver:
    __slots__ = ("_cache", "_failures")

    def __init__(self) -> None:
        self._cache: Dict[int, Tuple[str, float]] = {}
        self._failures: Set[int] = set()

    def resolve_many(self, bot: commands.Bot, ids: Iterable[int]) -> List[str]:
        return [self.resolve(bot, snowflake) for snowflake in ids]

    def resolve(self, bot: commands.Bot, snowflake: int) -> str:
        now = time.monotonic()
        cached = self._cache.get(snowflake)
        if cached and cached[1] > now:
            return cached[0]

        try:
            resolved = self._lookup(bot, snowflake)
        except Exception as exc:  # pragma: no cover - defensive logging
            if snowflake not in self._failures:
                self._failures.add(snowflake)
                logger.warning(
                    "failed to resolve discord id",
                    extra={"id": snowflake},
                    exc_info=exc,
                )
            resolved = "(not found)"

        self._cache[snowflake] = (resolved, now + _NAME_CACHE_TTL_SEC)
        return resolved

    def _lookup(self, bot: commands.Bot, snowflake: int) -> str:
        guild = bot.get_guild(snowflake)
        if guild is not None:
            return f"{guild.name} (guild)"

        channel = bot.get_channel(snowflake)
        if channel is not None:
            return _describe_channel(channel)

        for guild in getattr(bot, "guilds", []):
            role = guild.get_role(snowflake)
            if role is not None:
                return _describe_role(role)

            channel = guild.get_channel(snowflake)
            if channel is not None:
                return _describe_channel(channel)

            getter = getattr(guild, "get_thread", None)
            if callable(getter):
                thread = getter(snowflake)
                if thread is not None:
                    return _describe_channel(thread)

        return "(not found)"

class CoreOpsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._id_resolver = _IdResolver()

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

        caps = cache_service.capabilities()
        now = dt.datetime.now(UTC)

        def _humanize(seconds: Optional[int]) -> str:
            if seconds is None:
                return "-"
            total = max(0, int(seconds))
            units = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
            parts = []
            for suffix, length in units:
                if total >= length:
                    qty, total = divmod(total, length)
                    parts.append(f"{qty}{suffix}")
                if len(parts) == 2:
                    break
            if not parts:
                parts.append("0s")
            return "".join(parts)

        for bucket in ("clans", "templates", "clan_tags"):
            info_raw = caps.get(bucket) or {}
            info = info_raw if isinstance(info_raw, dict) else {}
            last_refresh = info.get("last_refresh_at")
            ttl_value = info.get("ttl_sec")
            next_refresh = info.get("next_refresh_at")

            age_seconds: Optional[int] = None
            if isinstance(last_refresh, dt.datetime):
                lr = last_refresh if last_refresh.tzinfo else last_refresh.replace(tzinfo=UTC)
                age_seconds = int((now - lr.astimezone(UTC)).total_seconds())
                if age_seconds < 0:
                    age_seconds = 0

            ttl_seconds: Optional[int] = None
            if isinstance(ttl_value, (int, float)):
                ttl_seconds = int(ttl_value)

            next_text = "-"
            if isinstance(next_refresh, dt.datetime):
                nr = next_refresh if next_refresh.tzinfo else next_refresh.replace(tzinfo=UTC)
                next_text = nr.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")

            embed.add_field(
                name=bucket,
                value=(
                    f"age: {_humanize(age_seconds)}, "
                    f"TTL: {_humanize(ttl_seconds)}, "
                    f"next: {next_text}"
                ),
                inline=False,
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
    @guild_only_denied_msg()
    @admin_only()
    async def env(self, ctx: commands.Context) -> None:
        bot_name = get_bot_name()
        env = get_env_name()
        version = os.getenv("BOT_VERSION", "dev")

        embed = discord.Embed(
            title=f"{bot_name} · {version} · {env}",
            colour=discord.Colour.dark_teal(),
        )

        sections: List[str] = []
        env_rows = self._collect_env_rows()
        sections.append("**Environment**\n" + _format_table(env_rows))

        sheet_sections = self._collect_sheet_sections()
        if sheet_sections:
            for label, rows in sheet_sections:
                sections.append(f"**{label} Config**\n" + _format_table(rows))
        else:
            sections.append("**Sheet Config**\n—")

        meta = _config_meta_from_app()
        source = meta.get("source", "runtime")
        status = meta.get("status", "ok")
        sections.append(f"**Config Loader**\n`{source}` · `{status}`")

        embed.description = "\n\n".join(sections)
        embed.timestamp = dt.datetime.now(UTC)
        embed.set_footer(text="values from ENV and Sheet Config")

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
    @guild_only_denied_msg()
    @ops_only()
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
    @guild_only_denied_msg()
    @ops_only()
    async def refresh(self, ctx: commands.Context) -> None:
        """Admin/Staff group: manual cache refresh."""

        if not _admin_roles_configured() and not can_manage_guild(getattr(ctx, "author", None)):
            await ctx.send("⚠️ Admin roles not configured — refresh commands disabled.")
            return
        await ctx.send("Available: `!rec refresh all`, `!rec refresh clansinfo`")

    @refresh.command(name="all")
    @guild_only_denied_msg()
    @ops_only()
    async def refresh_all(self, ctx: commands.Context) -> None:
        """Admin: clear & warm all registered Sheets caches."""

        caps = cache_service.capabilities()
        buckets = list(caps.keys())
        if not buckets:
            await ctx.send("⚠️ No cache buckets registered.")
            return
        await ctx.send(f"🧹 Refreshing: {', '.join(buckets)} (background).")
        actor = str(ctx.author)
        for name in buckets:
            asyncio.create_task(
                cache_service.cache.refresh_now(name, trigger="manual", actor=actor)
            )

    @refresh.command(name="clansinfo")
    @guild_only_denied_msg()
    @ops_only()
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
        asyncio.create_task(
            cache_service.cache.refresh_now("clans", trigger="manual", actor=str(ctx.author))
        )

    def _collect_env_rows(self) -> List[Tuple[str, str, str]]:
        snapshot = get_config_snapshot()
        rows: List[Tuple[str, str, str]] = []
        for key in _candidate_env_keys(snapshot):
            raw_value: object
            if key in os.environ:
                raw_value = os.environ.get(key)
            else:
                raw_value = snapshot.get(key)

            normalized = _normalize_snapshot_value(raw_value)
            display_value = redact_value(key, normalized)
            resolved = self._resolve_ids(_extract_ids(key, normalized))
            rows.append((key, display_value, resolved))
        return rows

    def _collect_sheet_sections(self) -> List[Tuple[str, List[Tuple[str, str, str]]]]:
        sections: List[Tuple[str, List[Tuple[str, str, str]]]] = []
        for label, module_name in _SHEET_CONFIG_SOURCES:
            snapshot = _sheet_cache_snapshot(module_name)
            if not snapshot:
                continue

            rows: List[Tuple[str, str, str]] = []
            for key in sorted(snapshot.keys()):
                display_key = str(key).upper()
                normalized = _normalize_snapshot_value(snapshot[key])
                display_value = redact_value(display_key, normalized)
                resolved = self._resolve_ids(_extract_ids(display_key, normalized))
                rows.append((display_key, display_value, resolved))

            if rows:
                sections.append((label, rows))

        return sections

    def _resolve_ids(self, ids: Sequence[int]) -> str:
        if not ids:
            return "—"
        names = self._id_resolver.resolve_many(self.bot, ids)
        return _format_resolved(names)

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            return
        raise error


__all__ = [
    "UTC",
    "CoreOpsCog",
    "_admin_check",
    "_admin_roles_configured",
    "_staff_check",
]
