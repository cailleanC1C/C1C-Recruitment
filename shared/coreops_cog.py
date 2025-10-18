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
from dataclasses import dataclass
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
    reload_config,
    get_onboarding_sheet_id,
    get_recruitment_sheet_id,
    redact_ids,
    redact_value,
)
from shared.coreops_render import (
    DigestEmbedData,
    DigestSheetEntry,
    DigestSheetsClientSummary,
    RefreshEmbedRow,
    build_digest_embed,
    build_digest_line,
    build_health_embed,
    build_refresh_embed,
)
from shared.cache import telemetry as cache_telemetry
from shared.help import (
    COREOPS_VERSION,
    HelpCommandInfo,
    HelpOverviewSection,
    build_coreops_footer,
    build_help_detail_embed,
    build_help_overview_embed,
)
from shared.coreops.helpers.tiers import tier
from shared.redaction import sanitize_embed, sanitize_log, sanitize_text
from shared.sheets.async_core import aget_worksheet
from shared.sheets.cache_service import cache as sheets_cache

from .coreops_rbac import (
    admin_only,
    can_view_admin,
    can_view_staff,
    guild_only_denied_msg,
    is_admin_member,
    is_staff_member,
    ops_only,
    staff_only,
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
_digest_section_errors_logged: Set[str] = set()
_FIELD_CHAR_LIMIT = 900
_DIGEST_SHEET_BUCKETS: Tuple[Tuple[str, str], ...] = (
    ("clans", "ClanInfo"),
    ("templates", "Templates"),
    ("clan_tags", "ClanTags"),
)
_CHECKSHEET_PING_TIMEOUT_SEC = 8.0


@dataclass(frozen=True)
class _ChecksheetBucket:
    key: str
    display: str
    sheet_id_source: str
    config_module: str
    config_keys: Tuple[str, ...]


_CHECKSHEET_BUCKETS: Tuple[_ChecksheetBucket, ...] = (
    _ChecksheetBucket(
        key="clans",
        display="ClanInfo",
        sheet_id_source="recruitment",
        config_module="sheets.recruitment",
        config_keys=("clans_tab",),
    ),
    _ChecksheetBucket(
        key="templates",
        display="Templates",
        sheet_id_source="recruitment",
        config_module="sheets.recruitment",
        config_keys=("welcome_templates_tab",),
    ),
    _ChecksheetBucket(
        key="clan_tags",
        display="ClanTags",
        sheet_id_source="onboarding",
        config_module="sheets.onboarding",
        config_keys=("clanlist_tab",),
    ),
)


@dataclass(frozen=True)
class _EnvEntry:
    key: str
    normalized: object
    display: str


def _format_bucket_label(name: str) -> str:
    cleaned = name.replace("_", " ").strip()
    if not cleaned:
        return name
    return " ".join(part.capitalize() for part in cleaned.split())


def _chunk_lines(lines: Sequence[str], limit: int) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        text = line.rstrip()
        additional = len(text) + (1 if current else 0)
        if current and current_len + additional > limit:
            chunks.append("\n".join(current))
            current = [text]
            current_len = len(text)
        else:
            current.append(text)
            current_len += additional
    if current:
        chunks.append("\n".join(current))
    return chunks or ["—"]


def _is_secret_key(key: str) -> bool:
    upper = key.upper()
    return (
        "TOKEN" in upper
        or "SECRET" in upper
        or "CREDENTIAL" in upper
        or "SERVICE_ACCOUNT" in upper
    )


def _trim_resolved_label(label: str) -> str:
    if label.endswith(" (guild)"):
        label = label[:-8]
    if " · " in label:
        label = label.split(" · ", 1)[0]
    return label


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


def _get_tier(cmd: commands.Command[Any, Any, Any]) -> str:
    extras = getattr(cmd, "extras", None)
    level = extras.get("tier") if isinstance(extras, dict) else None
    return level or getattr(cmd, "_tier", "user")


def _should_show(cmd: commands.Command[Any, Any, Any]) -> bool:
    # never show internals or the group container
    if cmd.qualified_name == "rec" or cmd.name.startswith("_"):
        return False

    # respect explicit opt-out flag in extras
    ex = getattr(cmd, "extras", None)
    if isinstance(ex, dict) and ex.get("hide_in_help"):
        return False

    # respect command.hidden only if command lacks a CoreOps/admin tier
    if getattr(cmd, "hidden", False):
        # find its tier (preserved via extras/_tier)
        tier = None
        ex = getattr(cmd, "extras", None)
        if isinstance(ex, dict):
            tier = ex.get("tier")
        tier = tier or getattr(cmd, "_tier", None)
        # hidden admin/staff commands stay visible to admins
        if tier not in {"admin", "staff"}:
            return False

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
        return bool(is_staff_member(author) or is_admin_member(author))

    return commands.check(predicate)


def staff_only() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        if is_staff_member(author) or is_admin_member(author):
            return True
        if getattr(ctx, "_coreops_suppress_denials", False):
            raise commands.CheckFailure("Staff only.")
        try:
            await ctx.reply("Staff only.")
        except Exception:
            pass
        raise commands.CheckFailure("Staff only.")

    return commands.check(predicate)


def _uptime_sec(bot: commands.Bot) -> float:
    started = getattr(bot, "_c1c_started_mono", None)
    return max(0.0, time.monotonic() - started) if started else 0.0


def _latency_sec(bot: commands.Bot) -> Optional[float]:
    try:
        return float(getattr(bot, "latency", None)) if bot.latency is not None else None
    except Exception:
        return None


def _delta_seconds(now: dt.datetime, value: dt.datetime | None) -> Optional[int]:
    if value is None:
        return None
    try:
        delta = value - now
        return int(delta.total_seconds())
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
            msg, extra = sanitize_log(
                "failed to import sheet config cache",
                extra={"module": module_name},
            )
            logger.warning(msg, extra=extra, exc_info=exc)
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
                msg, extra = sanitize_log(
                    "failed to resolve discord id",
                    extra={"id": snowflake},
                )
                logger.warning(msg, extra=extra, exc_info=exc)
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

    @commands.group(name="rec", invoke_without_command=True)
    @guild_only_denied_msg()
    async def rec(self, ctx: commands.Context) -> None:
        """Recruitment toolkit commands for the C1C cluster."""

        if ctx.invoked_subcommand is not None:
            return
        await ctx.send(
            str(
                sanitize_text(
                    "Use !rec help, !rec help <command>, or !rec help <command> <subcommand>."
                )
            )
        )

    async def _health_impl(self, ctx: commands.Context) -> None:
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

        snapshots = cache_telemetry.get_all_snapshots()

        for bucket in ("clans", "templates", "clan_tags"):
            snapshot = snapshots.get(bucket)
            if snapshot is None:
                snapshot = cache_telemetry.get_snapshot(bucket)

            age_text = snapshot.age_human or "-"
            ttl_text = snapshot.ttl_human or "-"
            next_text = "-"
            delta = snapshot.next_refresh_delta_seconds
            if delta is not None and snapshot.next_refresh_human:
                if delta >= 0:
                    next_text = f"in {snapshot.next_refresh_human}"
                else:
                    next_text = f"{snapshot.next_refresh_human} overdue"

            embed.add_field(
                name=bucket,
                value=(
                    f"age: {age_text}, "
                    f"TTL: {ttl_text}, "
                    f"next: {next_text}"
                ),
                inline=False,
            )
        await ctx.reply(embed=sanitize_embed(embed))

    def _format_refresh_summary(
        self, result: cache_telemetry.RefreshResult
    ) -> tuple[str, bool]:
        snapshot = result.snapshot
        label = _format_bucket_label(result.name) or result.name

        parts: list[str] = []
        if result.ok:
            duration_ms = result.duration_ms if result.duration_ms is not None else 0
            parts.append(f"refreshed in {duration_ms} ms")
        else:
            error_text = (result.error or "unknown error").strip()
            if len(error_text) > 120:
                error_text = f"{error_text[:117]}…"
            parts.append(f"error: {error_text}")

        if snapshot.ttl_human is not None:
            parts.append(f"ttl {snapshot.ttl_human}")
        if snapshot.age_human is not None:
            parts.append(f"age {snapshot.age_human}")

        next_at = snapshot.next_refresh_at
        if next_at is not None:
            next_utc = next_at.astimezone(UTC)
            parts.append(f"next {next_utc:%H:%M} UTC")
        elif snapshot.next_refresh_delta_seconds is not None and snapshot.next_refresh_human:
            delta = snapshot.next_refresh_delta_seconds
            if delta >= 0:
                parts.append(f"next in {snapshot.next_refresh_human}")
            else:
                parts.append(f"next overdue by {snapshot.next_refresh_human}")

        if not parts:
            parts.append("no telemetry")

        return f"{label} — {' · '.join(parts)}", result.ok

    def _parse_reload_flags(self, flags: Sequence[str]) -> tuple[bool, Optional[str]]:
        reboot = False
        for flag in flags:
            if flag == "--reboot":
                reboot = True
                continue
            return reboot, flag
        return reboot, None

    async def _reload_impl(self, ctx: commands.Context, *, reboot: bool) -> None:
        actor = str(ctx.author)
        actor_display = getattr(ctx.author, "display_name", None) or actor
        actor_id = getattr(ctx.author, "id", None)
        action = "reboot" if reboot else "reload"

        start = time.monotonic()
        try:
            reload_config()
        except Exception as exc:  # pragma: no cover - defensive guard
            msg, extra = sanitize_log(
                "config reload failed",
                extra={
                    "actor": actor,
                    "actor_id": int(actor_id) if isinstance(actor_id, int) else actor_id,
                    "action": action,
                },
            )
            logger.exception(msg, extra=extra)
            error_text = (str(exc).strip()) or exc.__class__.__name__
            await ctx.send(str(sanitize_text(f"⚠️ {action} failed — {error_text}")))
            return

        duration_ms = int((time.monotonic() - start) * 1000)
        status = "graceful reboot scheduled" if reboot else "config reloaded"
        message = f"{status} · {duration_ms} ms · by {actor_display}"
        await ctx.send(str(sanitize_text(message)))

        log_msg, extra = sanitize_log(
            "config reload completed",
            extra={
                "actor": actor,
                "actor_id": int(actor_id) if isinstance(actor_id, int) else actor_id,
                "action": action,
                "duration_ms": duration_ms,
            },
        )
        logger.info(log_msg, extra=extra)

        async def _shutdown() -> None:
            await self.bot.close()

        if reboot:
            await _shutdown()
            await asyncio.sleep(1)

    async def _refresh_single_impl(
        self, ctx: commands.Context, bucket: str
    ) -> None:
        candidate = bucket.strip()
        if not candidate:
            await self._refresh_root(ctx)
            return

        buckets = cache_telemetry.list_buckets()
        if not buckets:
            await ctx.send(str(sanitize_text("⚠️ No cache buckets registered.")))
            return

        lookup = {name.lower(): name for name in buckets}
        target = lookup.get(candidate.lower())
        if target is None:
            available = ", ".join(buckets)
            await ctx.send(
                str(
                    sanitize_text(
                        f"⚠️ Unknown bucket `{candidate}`. Available: {available}"
                    )
                )
            )
            return

        actor_display = getattr(ctx.author, "display_name", None) or str(ctx.author)
        actor = str(ctx.author)
        actor_id = getattr(ctx.author, "id", None)

        try:
            result = await cache_telemetry.refresh_now(target, actor=actor)
        except asyncio.CancelledError:
            raise

        summary, ok = self._format_refresh_summary(result)
        prefix = "•" if ok else "⚠"
        duration_ms = result.duration_ms if result.duration_ms is not None else 0
        header = f"cache refresh · {target} · {duration_ms} ms · by {actor_display}"
        message = "\n".join([header, f"{prefix} {summary}"])

        await self._send_refresh_response(
            ctx,
            scope=target,
            actor_display=actor_display,
            rows=[self._build_refresh_row(result)],
            total_duration=duration_ms,
            fallback_message=message,
        )

        log_msg, extra = sanitize_log(
            "cache refresh completed",
            extra={
                "actor": actor,
                "actor_id": int(actor_id) if isinstance(actor_id, int) else actor_id,
                "buckets": [target],
                "duration_ms": duration_ms,
                "failures": [] if ok else [target],
            },
        )
        logger.info(log_msg, extra=extra)

    @tier("admin")
    @rec.command(name="health")
    @staff_only()
    async def rec_health(self, ctx: commands.Context) -> None:
        await self._health_impl(ctx)

    @tier("admin")
    @commands.command(name="health", hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def health(self, ctx: commands.Context) -> None:
        await self._health_impl(ctx)

    def _trim_error_text(self, text: str, *, limit: int = 120) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        cleaned = cleaned.replace("`", "ʼ")
        if not cleaned:
            return "n/a"
        if len(cleaned) > limit:
            return f"{cleaned[: limit - 1].rstrip()}…"
        return cleaned

    def _select_next_refresh_candidate(
        self, candidates: Sequence[Tuple[Optional[int], Optional[dt.datetime]]], now: dt.datetime
    ) -> Tuple[Optional[int], Optional[dt.datetime]]:
        future = [item for item in candidates if item[0] is not None and item[0] >= 0]
        if future:
            return min(future, key=lambda item: item[0] or 0)
        known = [item for item in candidates if item[0] is not None]
        if known:
            return min(known, key=lambda item: abs(item[0] or 0))
        for delta, at in candidates:
            if at is None:
                continue
            computed = _delta_seconds(now, at)
            return computed, at
        return None, None

    def _log_digest_section_error(self, section: str, exc: BaseException) -> None:
        if section in _digest_section_errors_logged:
            return
        _digest_section_errors_logged.add(section)
        msg, extra = sanitize_log("failed to collect digest section", extra={"section": section})
        logger.warning(msg, extra=extra, exc_info=exc)

    def _collect_sheet_bucket_entries(self) -> Sequence[DigestSheetEntry]:
        entries: List[DigestSheetEntry] = []
        for bucket_key, display_name in _DIGEST_SHEET_BUCKETS:
            try:
                snapshot = cache_telemetry.get_snapshot(bucket_key)
            except Exception as exc:
                self._log_digest_section_error("sheets", exc)
                snapshot = None

            if snapshot is None or not hasattr(snapshot, "available"):
                entries.append(
                    DigestSheetEntry(
                        display_name=display_name,
                        status="n/a",
                        age_seconds=None,
                        next_refresh_delta_seconds=None,
                        next_refresh_at=None,
                        retries=None,
                        error=None,
                        age_estimated=False,
                        next_refresh_estimated=False,
                    )
                )
                continue

            available = getattr(snapshot, "available", False)

            raw_age = getattr(snapshot, "age_seconds", None) if available else None
            age_seconds = None
            if isinstance(raw_age, (int, float)):
                try:
                    age_seconds = int(raw_age)
                except Exception:
                    age_seconds = None

            raw_next_delta = (
                getattr(snapshot, "next_refresh_delta_seconds", None) if available else None
            )
            next_delta = None
            if isinstance(raw_next_delta, (int, float)):
                try:
                    next_delta = int(raw_next_delta)
                except Exception:
                    next_delta = None

            next_at = getattr(snapshot, "next_refresh_at", None) if available else None
            last_error = getattr(snapshot, "last_error", None)
            last_result = getattr(snapshot, "last_result", None)
            retries_raw = getattr(snapshot, "retries", None)
            retries = None
            if isinstance(retries_raw, int):
                retries = retries_raw

            status = "n/a"
            error_text: Optional[str] = None

            result_norm = (last_result or "").strip().lower()
            has_error = bool(last_error) or result_norm.startswith("fail")

            if available:
                status = "fail" if has_error else "ok"
            elif has_error:
                status = "fail"

            if has_error:
                source = last_error or last_result or "fail"
                error_text = self._trim_error_text(source)

            entries.append(
                DigestSheetEntry(
                    display_name=display_name,
                    status=status,
                    age_seconds=age_seconds,
                    next_refresh_delta_seconds=next_delta,
                    next_refresh_at=next_at,
                    retries=retries,
                    error=error_text,
                    age_estimated=False,
                    next_refresh_estimated=False,
                )
            )

        return entries

    def _resolve_sheet_id_for_bucket(self, bucket: _ChecksheetBucket) -> Optional[str]:
        if bucket.sheet_id_source == "recruitment":
            sheet_id = get_recruitment_sheet_id()
        elif bucket.sheet_id_source == "onboarding":
            sheet_id = get_onboarding_sheet_id()
        else:
            sheet_id = ""
        sheet_id = str(sheet_id or "").strip()
        return sheet_id or None

    def _resolve_tab_name_for_bucket(self, bucket: _ChecksheetBucket) -> Optional[str]:
        snapshot = _sheet_cache_snapshot(bucket.config_module)
        for key in bucket.config_keys:
            candidates = {key, key.lower(), key.upper()}
            for candidate in candidates:
                value = snapshot.get(candidate)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        config_snapshot = get_config_snapshot()
        for key in bucket.config_keys:
            candidate = key.upper()
            value = config_snapshot.get(candidate)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _count_rows(self, data: object) -> Optional[int]:
        if data is None:
            return None
        if isinstance(data, (str, bytes)):
            return None
        try:
            return len(data)  # type: ignore[arg-type]
        except Exception:
            return None

    def _get_cached_row_count(self, bucket: _ChecksheetBucket) -> Optional[int]:
        try:
            cache_bucket = sheets_cache.get_bucket(bucket.key)
        except Exception:
            return None
        if cache_bucket is None:
            return None
        value = getattr(cache_bucket, "value", None)
        count = self._count_rows(value)
        if count is None:
            return None
        if bucket.key == "clans" and isinstance(value, list):
            return max(0, int(count) - 1)
        return int(count)

    def _derive_last_status(
        self, snapshot: cache_telemetry.CacheSnapshot
    ) -> tuple[str, Optional[str]]:
        error = snapshot.last_error or ""
        if error:
            return "fail", self._trim_error_text(error)

        result = (snapshot.last_result or "").strip().lower()
        if result:
            if result in {"ok", "retry_ok"}:
                return "ok", None
            return "fail", self._trim_error_text(snapshot.last_result or result)

        if snapshot.available:
            return "ok", None
        return "n/a", None

    async def _probe_bucket(
        self, bucket: _ChecksheetBucket, *, sheet_id: Optional[str], tab_name: Optional[str]
    ) -> tuple[bool, Optional[str]]:
        if not sheet_id:
            return False, "missing sheet id"
        if not tab_name:
            return False, "missing tab name"
        try:
            await asyncio.wait_for(
                aget_worksheet(sheet_id, tab_name), timeout=_CHECKSHEET_PING_TIMEOUT_SEC
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            return False, "timeout"
        except Exception as exc:
            return False, self._trim_error_text(exc)
        return True, None

    async def _checksheet_impl(self, ctx: commands.Context) -> None:
        env = get_env_name()
        bot_version = os.getenv("BOT_VERSION", "dev")
        lines: list[str] = []

        for bucket in _CHECKSHEET_BUCKETS:
            snapshot = cache_telemetry.get_snapshot(bucket.key)
            row_count = self._get_cached_row_count(bucket)
            age_text = snapshot.age_human or "n/a"
            last_status, last_error = self._derive_last_status(snapshot)

            sheet_id = self._resolve_sheet_id_for_bucket(bucket)
            tab_name = self._resolve_tab_name_for_bucket(bucket)
            ok, error_text = await self._probe_bucket(
                bucket, sheet_id=sheet_id, tab_name=tab_name
            )

            status_marker = "🟢" if ok else "🔴"
            status_text = "ok" if ok else "fail"
            rows_text = str(row_count) if row_count is not None else "n/a"

            parts = [
                f"{bucket.display} — {status_marker} {status_text}",
                f"rows {rows_text}",
                f"age {age_text}",
                f"last {last_status}",
            ]

            if last_error:
                parts.append(f"last_err {last_error}")
            if error_text:
                parts.append(f"error {error_text}")

            lines.append(" · ".join(parts))

        embed = discord.Embed(title="Checksheet", colour=discord.Colour.dark_teal())
        description_lines = [f"env: {env}"]
        description_lines.extend(lines)
        embed.description = "\n".join(description_lines)

        footer_text = build_coreops_footer(bot_version=bot_version, coreops_version=COREOPS_VERSION)
        embed.set_footer(text=footer_text)

        await ctx.reply(embed=sanitize_embed(embed))

    @tier("staff")
    @rec.command(name="checksheet")
    @guild_only_denied_msg()
    @staff_only()
    async def rec_checksheet(self, ctx: commands.Context) -> None:
        await self._checksheet_impl(ctx)

    @tier("staff")
    @commands.command(name="checksheet", hidden=True)
    @guild_only_denied_msg()
    @ops_only()
    async def checksheet(self, ctx: commands.Context) -> None:
        await self._checksheet_impl(ctx)

    def _collect_sheets_client_summary(self, now: dt.datetime) -> Optional[DigestSheetsClientSummary]:
        try:
            capabilities = sheets_cache.capabilities()
        except Exception as exc:
            self._log_digest_section_error("sheets_client", exc)
            return None

        if not isinstance(capabilities, dict):
            return None

        buckets: List[object] = []
        for key in capabilities.keys():
            if not isinstance(key, str):
                continue
            try:
                bucket = sheets_cache.get_bucket(key)
            except Exception:
                bucket = None
            if bucket is None:
                continue
            buckets.append(bucket)

        if not buckets:
            return None

        latest_refresh_at: Optional[dt.datetime] = None
        latest_latency: Optional[int] = None
        latest_retries: Optional[int] = None
        latest_error: Optional[str] = None
        latest_result: Optional[str] = None
        failure_error: Optional[str] = None

        for bucket in buckets:
            last_refresh = getattr(bucket, "last_refresh", None)
            if isinstance(last_refresh, dt.datetime) and (
                latest_refresh_at is None or last_refresh > latest_refresh_at
            ):
                latest_refresh_at = last_refresh
                latency_ms = getattr(bucket, "last_latency_ms", None)
                latest_latency = (
                    int(latency_ms)
                    if isinstance(latency_ms, (int, float))
                    else None
                )
                retries_val = getattr(bucket, "last_retries", None)
                latest_retries = (
                    int(retries_val)
                    if isinstance(retries_val, (int, float))
                    else None
                )
                latest_result = getattr(bucket, "last_result", None)
                latest_error = getattr(bucket, "last_error", None)

            result_text = getattr(bucket, "last_result", None)
            result_norm = (result_text or "").strip().lower()
            if result_norm and result_norm not in {"ok", "retry_ok"} and failure_error is None:
                err_source = getattr(bucket, "last_error", None) or result_text
                failure_error = self._trim_error_text(err_source)

        last_success_age: Optional[int] = None
        if isinstance(latest_refresh_at, dt.datetime):
            try:
                last_success_age = max(0, int((now - latest_refresh_at).total_seconds()))
            except Exception:
                last_success_age = None

        summary_error = failure_error
        if summary_error is None and latest_error:
            summary_error = self._trim_error_text(latest_error)
        if summary_error is None and latest_result:
            summary_error = self._trim_error_text(latest_result)

        return DigestSheetsClientSummary(
            last_success_age=last_success_age,
            latency_ms=latest_latency,
            retries=latest_retries,
            last_error=summary_error,
        )

    async def _digest_impl(self, ctx: commands.Context) -> None:
        env = get_env_name()
        uptime = _uptime_sec(self.bot)
        latency = _latency_sec(self.bot)
        try:
            gateway_age = await hb.age_seconds()
        except Exception:
            gateway_age = None

        now = dt.datetime.now(UTC)
        uptime_seconds = int(uptime) if uptime is not None else None
        sheet_entries = self._collect_sheet_bucket_entries()
        sheets_summary = self._collect_sheets_client_summary(now)
        bot_version = os.getenv("BOT_VERSION", "dev")

        embed_data = DigestEmbedData(
            env=env,
            uptime_seconds=uptime_seconds,
            latency_seconds=latency,
            gateway_age_seconds=int(gateway_age) if gateway_age is not None else None,
            sheets=tuple(sheet_entries),
            sheets_client=sheets_summary,
            bot_version=bot_version,
        )

        fallback_line = build_digest_line(
            env=env,
            uptime_sec=uptime,
            latency_s=latency,
            last_event_age=gateway_age if isinstance(gateway_age, (int, float)) else None,
        )

        try:
            embed = build_digest_embed(data=embed_data)
        except Exception:
            msg, extra = sanitize_log("failed to build digest embed", extra={"command": "digest"})
            logger.exception(msg, extra=extra)
            await ctx.reply(str(sanitize_text(fallback_line)))
            return

        try:
            await ctx.reply(embed=sanitize_embed(embed))
        except Exception:
            msg, extra = sanitize_log("failed to send digest embed", extra={"command": "digest"})
            logger.exception(msg, extra=extra)
            await ctx.reply(str(sanitize_text(fallback_line)))

    @tier("staff")
    @rec.command(name="digest")
    @staff_only()
    async def rec_digest(self, ctx: commands.Context) -> None:
        await self._digest_impl(ctx)

    @tier("admin")
    @commands.command(name="digest", hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def digest(self, ctx: commands.Context) -> None:
        await self._digest_impl(ctx)

    async def _env_impl(self, ctx: commands.Context) -> None:
        bot_name = get_bot_name()
        env = get_env_name()
        version = os.getenv("BOT_VERSION", "dev")
        guild_name = getattr(getattr(ctx, "guild", None), "name", "unknown")

        embed = discord.Embed(
            title=f"{bot_name} · env: {env} · Guild: {guild_name}",
            colour=discord.Colour.dark_teal(),
        )

        entries = self._collect_env_entries()
        sheet_sections = self._collect_sheet_sections()

        groups = [
            ("Core Identity", self._format_core_identity(entries)),
            ("Guild / Channels", self._format_guild_channels(entries)),
            ("Roles", self._format_roles(entries)),
            ("Sheets / Config Keys", self._format_sheet_keys(entries, sheet_sections)),
            ("Features / Flags", self._format_features(entries)),
            ("Cache / Refresh", self._format_cache_refresh(entries)),
            ("Watchdog / Runtime", self._format_watchdog(entries)),
            ("Render / Infra", self._format_render(entries)),
            ("Secrets (masked)", self._format_secrets(entries)),
        ]

        for name, lines in groups:
            self._add_embed_group(embed, name, lines)

        embed.timestamp = dt.datetime.now(UTC)
        footer_text = build_coreops_footer(
            bot_version=version, notes=" • source: ENV + Sheet Config"
        )
        embed.set_footer(text=footer_text)

        await ctx.reply(embed=sanitize_embed(embed))

    @tier("admin")
    @rec.command(name="env")
    @guild_only_denied_msg()
    @admin_only()
    async def rec_env(self, ctx: commands.Context) -> None:
        await self._env_impl(ctx)

    @tier("admin")
    @commands.command(name="env", hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def env(self, ctx: commands.Context) -> None:
        await self._env_impl(ctx)

    @tier("user")
    @rec.command(name="help", usage="[command]")
    async def rec_help(
        self, ctx: commands.Context, *, query: str | None = None
    ) -> None:
        await self.render_help(ctx, query=query)

    async def render_help(
        self, ctx: commands.Context, *, query: str | None = None
    ) -> None:
        await self._render_help(ctx, query=query)

    @tier("user")
    @rec.command(name="ping")
    async def rec_ping(self, ctx: commands.Context) -> None:
        command = self.bot.get_command("ping")
        if command is None:
            await ctx.send(str(sanitize_text("Ping command unavailable.")))
            return
        await ctx.invoke(command)

    async def _render_help(
        self, ctx: commands.Context, *, query: str | None
    ) -> None:
        prefix = get_command_prefix()
        bot_version = os.getenv("BOT_VERSION", "dev")
        bot_name = get_bot_name()
        lookup = query.strip() if isinstance(query, str) else ""

        if not lookup:
            sections = await self._gather_overview_sections(ctx)
            if not sections:
                await ctx.reply(str(sanitize_text("No commands available.")))
                return
            embed = build_help_overview_embed(
                prefix=prefix,
                sections=sections,
                bot_version=bot_version,
                bot_name=bot_name,
                bot_description=self._help_bot_description(bot_name=bot_name),
            )
            await ctx.reply(embed=sanitize_embed(embed))
            return

        normalized_lookup = " ".join(lookup.lower().split())
        command = self.bot.get_command(normalized_lookup)
        if command is None and not normalized_lookup.startswith("rec "):
            command = self.bot.get_command(f"rec {normalized_lookup}")
        if command is None:
            await ctx.reply(str(sanitize_text(f"Unknown command `{lookup}`.")))
            return

        if not await self._can_display_command(command, ctx):
            await ctx.reply(str(sanitize_text("You do not have access to that command.")))
            return

        command_info = self._build_help_info(command)
        subcommands = await self._gather_subcommand_infos(command, ctx)
        embed = build_help_detail_embed(
            prefix=prefix,
            command=command_info,
            subcommands=subcommands,
            bot_version=bot_version,
            bot_name=bot_name,
        )
        await ctx.reply(embed=sanitize_embed(embed))

    async def _config_impl(self, ctx: commands.Context) -> None:
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

        await ctx.reply(str(sanitize_text("\n".join(lines))))

    @tier("staff")
    @rec.command(name="config")
    @guild_only_denied_msg()
    @ops_only()
    async def rec_config(self, ctx: commands.Context) -> None:
        await self._config_impl(ctx)

    @tier("admin")
    @commands.command(name="config", hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def config_summary(self, ctx: commands.Context) -> None:
        await self._config_impl(ctx)

    async def _refresh_root(self, ctx: commands.Context) -> None:
        author = getattr(ctx, "author", None)
        if not _admin_roles_configured() and not (
            is_admin_member(author) or is_staff_member(author)
        ):
            await ctx.send(
                str(sanitize_text("⚠️ Admin roles not configured — refresh commands disabled."))
            )
            return
        await ctx.send(
            str(sanitize_text("Available: `!refresh all`, `!refresh clansinfo`"))
        )

    @tier("admin")
    @commands.command(name="reload", hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def reload(self, ctx: commands.Context, *flags: str) -> None:
        reboot, unknown = self._parse_reload_flags(flags)
        if unknown is not None:
            await ctx.send(
                str(sanitize_text(f"⚠️ Unknown flag: {unknown}"))
            )
            return

        await self._reload_impl(ctx, reboot=reboot)

    @tier("admin")
    @rec.command(name="reload")
    @guild_only_denied_msg()
    @ops_only()
    async def rec_reload(self, ctx: commands.Context, *flags: str) -> None:
        reboot, unknown = self._parse_reload_flags(flags)
        if unknown is not None:
            await ctx.send(
                str(sanitize_text(f"⚠️ Unknown flag: {unknown}"))
            )
            return

        await self._reload_impl(ctx, reboot=reboot)

    @tier("admin")
    @commands.group(name="refresh", invoke_without_command=True, hidden=True)
    @guild_only_denied_msg()
    @admin_only()
    async def refresh(
        self, ctx: commands.Context, *, bucket: Optional[str] = None
    ) -> None:
        """Admin group: manual cache refresh."""

        if bucket and bucket.strip():
            await self._refresh_single_impl(ctx, bucket)
            return
        await self._refresh_root(ctx)

    @tier("admin")
    @rec.group(name="refresh", invoke_without_command=True)
    @guild_only_denied_msg()
    @ops_only()
    async def rec_refresh(
        self, ctx: commands.Context, *, bucket: Optional[str] = None
    ) -> None:
        if bucket and bucket.strip():
            await self._refresh_single_impl(ctx, bucket)
            return
        await self._refresh_root(ctx)

    async def _refresh_all_impl(self, ctx: commands.Context) -> None:
        buckets = cache_telemetry.list_buckets()
        if not buckets:
            await ctx.send(str(sanitize_text("⚠️ No cache buckets registered.")))
            return

        actor_display = getattr(ctx.author, "display_name", None) or str(ctx.author)
        actor = str(ctx.author)
        actor_id = getattr(ctx.author, "id", None)

        overall_start = time.monotonic()
        summaries: list[str] = []
        failures: list[str] = []
        embed_rows: list[RefreshEmbedRow] = []

        for name in buckets:
            try:
                result = await cache_telemetry.refresh_now(name, actor=actor)
            except asyncio.CancelledError:
                raise

            summary, ok = self._format_refresh_summary(result)
            prefix = "•" if ok else "⚠"
            summaries.append(f"{prefix} {summary}")
            if not ok:
                failures.append(name)
            embed_rows.append(self._build_refresh_row(result))

        total_duration = int((time.monotonic() - overall_start) * 1000)
        header = (
            f"cache refresh · {len(buckets)} bucket(s) · {total_duration} ms · by {actor_display}"
        )

        message = "\n".join([header, *summaries])
        await self._send_refresh_response(
            ctx,
            scope="all",
            actor_display=actor_display,
            rows=embed_rows,
            total_duration=total_duration,
            fallback_message=message,
        )

        log_msg, extra = sanitize_log(
            "cache refresh completed",
            extra={
                "actor": actor,
                "actor_id": int(actor_id) if isinstance(actor_id, int) else actor_id,
                "buckets": buckets,
                "duration_ms": total_duration,
                "failures": failures,
            },
        )
        logger.info(log_msg, extra=extra)

    @tier("admin")
    @refresh.command(name="all")
    @guild_only_denied_msg()
    @admin_only()
    @commands.cooldown(1, 30.0, commands.BucketType.guild)
    async def refresh_all(self, ctx: commands.Context) -> None:
        """Admin: clear & warm all registered Sheets caches."""

        await self._refresh_all_impl(ctx)

    @tier("admin")
    @rec_refresh.command(name="all")
    @guild_only_denied_msg()
    @ops_only()
    @commands.cooldown(1, 30.0, commands.BucketType.guild)
    async def rec_refresh_all(self, ctx: commands.Context) -> None:
        await self._refresh_all_impl(ctx)

    def _build_refresh_row(
        self, result: cache_telemetry.RefreshResult
    ) -> RefreshEmbedRow:
        snapshot = result.snapshot
        label = _format_bucket_label(result.name) or result.name or "-"
        duration_ms = result.duration_ms if result.duration_ms is not None else 0
        duration_text = f"{duration_ms} ms"

        raw_result = (snapshot.last_result or ("ok" if result.ok else "fail")).strip()
        display_result = raw_result.replace("_", " ") if raw_result else "-"

        normalized = raw_result.lower()
        retries = "1" if normalized in {"retry_ok", "fail"} else "0"

        error_text = result.error or snapshot.last_error or "-"
        cleaned_error = " ".join(str(error_text).split()) if error_text else "-"
        if len(cleaned_error) > 70:
            cleaned_error = f"{cleaned_error[:67]}…"

        return RefreshEmbedRow(
            bucket=label,
            duration=duration_text,
            result=display_result or "-",
            retries=retries,
            error=cleaned_error or "-",
        )

    async def _send_refresh_response(
        self,
        ctx: commands.Context,
        *,
        scope: str,
        actor_display: str,
        rows: Sequence[RefreshEmbedRow],
        total_duration: int,
        fallback_message: str,
    ) -> None:
        bot_version = os.getenv("BOT_VERSION", "dev")
        now_utc = dt.datetime.now(UTC)

        embed = None
        try:
            embed = build_refresh_embed(
                scope=scope,
                actor_display=actor_display,
                trigger="manual",
                rows=rows,
                total_ms=total_duration,
                bot_version=bot_version,
                coreops_version=COREOPS_VERSION,
                now_utc=now_utc,
            )
        except Exception:
            embed = None

        sent = False
        if embed is not None:
            try:
                await ctx.send(embed=sanitize_embed(embed))
            except Exception:
                sent = False
            else:
                sent = True

        if not sent:
            await ctx.send(str(sanitize_text(fallback_message)))

    async def _refresh_clansinfo_impl(self, ctx: commands.Context) -> None:
        snapshot = cache_telemetry.get_snapshot("clans")
        if not snapshot.available:
            await ctx.send(str(sanitize_text("⚠️ No clansinfo cache registered.")))
            return

        age_seconds = snapshot.age_seconds if snapshot.age_seconds is not None else 10**9
        if age_seconds < 60 * 60:
            mins = age_seconds // 60
            nxt = ""
            if snapshot.next_refresh_delta_seconds is not None and snapshot.next_refresh_human:
                delta = snapshot.next_refresh_delta_seconds
                if delta >= 0:
                    nxt = f" Next auto-refresh in {snapshot.next_refresh_human}"
                else:
                    nxt = f" Next auto-refresh overdue by {snapshot.next_refresh_human}"
            await ctx.send(str(sanitize_text(f"✅ Clans cache fresh ({mins}m old).{nxt}")))
            return

        await ctx.send(str(sanitize_text("Refreshing clans (background).")))
        asyncio.create_task(
            cache_telemetry.refresh_now("clans", actor=str(ctx.author))
        )

    @tier("admin")
    @refresh.command(name="clansinfo")
    @guild_only_denied_msg()
    @admin_only()
    async def refresh_clansinfo(self, ctx: commands.Context) -> None:
        """Staff/Admin: refresh 'clans' cache if age ≥ 60 min."""

        await self._refresh_clansinfo_impl(ctx)

    @tier("staff")
    @rec_refresh.command(name="clansinfo")
    @guild_only_denied_msg()
    @ops_only()
    async def rec_refresh_clansinfo(self, ctx: commands.Context) -> None:
        await self._refresh_clansinfo_impl(ctx)

    async def _gather_overview_sections(
        self, ctx: commands.Context
    ) -> list[HelpOverviewSection]:
        grouped: dict[str, list[commands.Command[Any, Any, Any]]] = {
            "user": [],
            "staff": [],
            "admin": [],
        }

        commands_iter: list[commands.Command[Any, Any, Any]] = []
        for command in self.bot.walk_commands():
            if not _should_show(command):
                continue
            if not self._include_in_overview(command):
                continue
            commands_iter.append(command)

        commands_iter.sort(key=lambda cmd: cmd.qualified_name)

        seen: set[str] = set()
        for command in commands_iter:
            base_name = command.qualified_name
            if base_name in seen:
                continue
            seen.add(base_name)
            if not await self._can_display_command(command, ctx):
                continue
            level = _get_tier(command)
            if level not in grouped:
                level = "user"
            grouped[level].append(command)

        author = getattr(ctx, "author", None)
        allowed: set[str] = {"user"}
        if can_view_staff(author):
            allowed.add("staff")
        if can_view_admin(author):
            allowed.add("admin")

        tier_order: list[tuple[str, str, str]] = [
            ("admin", "Admin", "Operational controls reserved for administrators."),
            (
                "staff",
                "Recruiter/Staff",
                "Tools for recruiters and staff managing applicant workflows.",
            ),
            ("user", "User", "Player-facing commands for everyday recruitment checks."),
        ]

        seen: set[str] = set()
        sections: list[HelpOverviewSection] = []
        for key, label, blurb in tier_order:
            if key not in allowed:
                continue
            commands_for_tier = grouped.get(key, [])
            if not commands_for_tier:
                continue
            filtered_commands: list[commands.Command[Any, Any, Any]] = []
            for command in sorted(
                commands_for_tier, key=lambda command: command.qualified_name
            ):
                base_name = command.qualified_name
                if base_name in seen:
                    continue
                seen.add(base_name)
                filtered_commands.append(command)
            if not filtered_commands:
                continue
            infos = [self._build_help_info(command) for command in filtered_commands]
            sections.append(
                HelpOverviewSection(
                    label=label,
                    blurb=blurb,
                    commands=tuple(infos),
                )
            )
        return sections

    def _include_in_overview(self, command: commands.Command[Any, Any, Any]) -> bool:
        if command.parent is None:
            return True

        top = command
        while top.parent is not None:
            top = top.parent
        return top.qualified_name == "rec"

    async def _gather_subcommand_infos(
        self, command: commands.Command[Any, Any, Any], ctx: commands.Context
    ) -> list[HelpCommandInfo]:
        if not isinstance(command, commands.Group):
            return []

        infos: list[HelpCommandInfo] = []
        seen: set[str] = set()
        for subcommand in command.commands:
            if not _should_show(subcommand):
                continue
            # Guard against duplicate references when aliases are registered.
            base_name = subcommand.qualified_name
            if base_name in seen:
                continue
            seen.add(base_name)
            if not await self._can_display_command(subcommand, ctx):
                continue
            infos.append(self._build_help_info(subcommand))

        infos.sort(key=lambda item: item.qualified_name)
        return infos

    async def _can_display_command(
        self, command: commands.Command[Any, Any, Any], ctx: commands.Context
    ) -> bool:
        if not command.enabled:
            return False
        author = getattr(ctx, "author", None)
        tier = _get_tier(command)
        if tier == "admin" and not can_view_admin(author):
            return False
        if tier == "staff" and not can_view_staff(author):
            return False
        sentinel = object()
        previous = getattr(ctx, "_coreops_suppress_denials", sentinel)
        setattr(ctx, "_coreops_suppress_denials", True)
        try:
            return await command.can_run(ctx)
        except commands.CheckFailure:
            return False
        except commands.CommandError:
            return False
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("failed help gate for command", exc_info=True)
            return False
        finally:
            if previous is sentinel:
                try:
                    delattr(ctx, "_coreops_suppress_denials")
                except AttributeError:
                    pass
            else:
                setattr(ctx, "_coreops_suppress_denials", previous)

    def _build_help_info(self, command: commands.Command[Any, Any, Any]) -> HelpCommandInfo:
        signature = command.signature or ""
        summary = command.short_doc or command.help or command.brief or ""
        aliases = tuple(sorted(alias.strip() for alias in command.aliases if alias.strip()))
        return HelpCommandInfo(
            qualified_name=command.qualified_name,
            signature=signature,
            summary=summary.strip(),
            aliases=aliases,
        )

    def _help_bot_description(self, *, bot_name: str) -> str:
        return (
            "C1C-Recruitment keeps the doors open and the hearths warm.\n"
            "It’s how we find new clanmates, help old friends move up, and keep every hall filled with good company.\n"
            "Members can peek at which clans have room, check what’s needed to join, or dig into details about any clan across the cluster.\n"
            "Recruiters use it to spot open slots, match new arrivals, and drop welcome notes so nobody gets lost on day one.\n"
            "All handled right here on Discord — fast, friendly, and stitched together with that usual C1C chaos and care."
        )

    def _add_embed_group(
        self, embed: discord.Embed, name: str, lines: Sequence[str]
    ) -> None:
        text_lines = list(lines)
        if not text_lines:
            text_lines = ["—"]
        elif all(line == "" for line in text_lines):
            text_lines = ["—"]

        chunks = _chunk_lines(text_lines, _FIELD_CHAR_LIMIT)
        for index, chunk in enumerate(chunks):
            label = name if index == 0 else f"{name} (cont.)"
            embed.add_field(name=label, value=f"```{chunk}```", inline=False)

    def _collect_env_entries(self) -> Dict[str, _EnvEntry]:
        snapshot = get_config_snapshot()
        entries: Dict[str, _EnvEntry] = {}
        for key in _candidate_env_keys(snapshot):
            if key in entries:
                continue
            raw_value: object
            if key in os.environ:
                raw_value = os.environ.get(key)
            else:
                raw_value = snapshot.get(key)

            normalized = _normalize_snapshot_value(raw_value)
            display_value = str(redact_value(key, normalized))
            entries[key] = _EnvEntry(key=key, normalized=normalized, display=display_value)
        return entries

    def _format_simple_line(self, key: str, entry: Optional[_EnvEntry]) -> str:
        value = entry.display if entry else "—"
        return f"{key} = {value}"

    def _format_core_identity(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        keys = ("BOT_NAME", "BOT_VERSION", "COMMAND_PREFIX", "ENV_NAME")
        return [self._format_simple_line(key, entries.get(key)) for key in keys]

    def _format_guild_channels(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        ordered = [
            "GUILD_IDS",
            "LOG_CHANNEL_ID",
            "WELCOME_CHANNEL_ID",
            "WELCOME_GENERAL_CHANNEL_ID",
            "NOTIFY_CHANNEL_ID",
            "PROMO_CHANNEL_ID",
            "RECRUITERS_THREAD_ID",
            "PANEL_FIXED_THREAD_ID",
            "PANEL_THREAD_MODE",
        ]
        lines: List[str] = []
        seen: Set[str] = set()
        for key in ordered:
            seen.add(key)
            lines.extend(self._format_channel_entry(key, entries.get(key)))

        dynamic = [
            key
            for key in entries.keys()
            if key not in seen
            and not _is_secret_key(key)
            and any(token in key for token in ("CHANNEL", "THREAD", "GUILD"))
        ]
        for key in sorted(dynamic):
            seen.add(key)
            lines.extend(self._format_channel_entry(key, entries.get(key)))

        return lines or ["—"]

    def _format_channel_entry(self, key: str, entry: Optional[_EnvEntry]) -> List[str]:
        if key == "PANEL_THREAD_MODE":
            return [self._format_simple_line(key, entry)]
        if entry is None:
            return [f"{key} = —"]
        ids = self._extract_visible_ids(key, entry.normalized)
        if not ids:
            return [self._format_simple_line(key, entry)]
        return self._format_id_lines(key, ids)

    def _format_roles(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        ordered = [
            "ADMIN_ROLE_IDS",
            "STAFF_ROLE_IDS",
            "LEAD_ROLE_IDS",
            "RECRUITER_ROLE_IDS",
            "NOTIFY_PING_ROLE_ID",
        ]
        lines: List[str] = []
        seen: Set[str] = set()
        for key in ordered:
            seen.add(key)
            lines.extend(self._format_role_entry(key, entries.get(key)))

        dynamic = [
            key
            for key in entries.keys()
            if key not in seen and not _is_secret_key(key) and "ROLE" in key
        ]
        for key in sorted(dynamic):
            lines.extend(self._format_role_entry(key, entries.get(key)))

        return lines or ["—"]

    def _format_role_entry(self, key: str, entry: Optional[_EnvEntry]) -> List[str]:
        if entry is None:
            return [f"{key} = —"]
        ids = self._extract_visible_ids(key, entry.normalized)
        if not ids:
            return [self._format_simple_line(key, entry)]
        return self._format_id_lines(key, ids)

    def _format_sheet_keys(
        self,
        entries: Dict[str, _EnvEntry],
        sheet_sections: List[Tuple[str, List[Tuple[str, str, str]]]],
    ) -> List[str]:
        ordered = ["RECRUITMENT_SHEET_ID", "ONBOARDING_SHEET_ID"]
        lines: List[str] = []
        seen: Set[str] = set()
        for key in ordered:
            seen.add(key)
            lines.append(self._format_simple_line(key, entries.get(key)))

        dynamic = [
            key
            for key in entries.keys()
            if key not in seen
            and not _is_secret_key(key)
            and ("SHEET" in key or "TAB" in key)
        ]
        for key in sorted(dynamic):
            lines.append(self._format_simple_line(key, entries.get(key)))

        if sheet_sections:
            if lines:
                lines.append("")
            for label, rows in sheet_sections:
                lines.append(f"{label} overrides:")
                for row_key, value, resolved in rows:
                    text = f"  {row_key} = {value}"
                    if resolved and resolved != "—":
                        text += f" ({resolved})"
                    lines.append(text)
                if rows:
                    lines.append("")
            while lines and not lines[-1].strip():
                lines.pop()

        meta = _config_meta_from_app()
        source = str(meta.get("source", "runtime"))
        status = str(meta.get("status", "ok"))
        if lines:
            lines.append("")
        lines.append(f"Loader: {source} · {status}")
        loaded_at = meta.get("loaded_at")
        if loaded_at:
            lines.append(f"  loaded_at: {loaded_at}")
        last_error = meta.get("last_error")
        if last_error:
            lines.append(f"  last_error: {last_error}")

        return lines or ["—"]

    def _format_features(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        ordered = [
            "WELCOME_ENABLED",
            "ENABLE_WELCOME_WATCHER",
            "ENABLE_PROMO_WATCHER",
            "ENABLE_NOTIFY_FALLBACK",
            "STRICT_PROBE",
            "PANEL_THREAD_MODE",
            "SEARCH_RESULTS_SOFT_CAP",
        ]
        lines = [self._format_simple_line(key, entries.get(key)) for key in ordered]
        seen = set(ordered)
        dynamic = [
            key
            for key in entries.keys()
            if key not in seen
            and not _is_secret_key(key)
            and (
                key.startswith("ENABLE_")
                or key.endswith("_ENABLED")
                or key in {"STRICT_PROBE", "PANEL_THREAD_MODE"}
            )
        ]
        for key in sorted(dynamic):
            lines.append(self._format_simple_line(key, entries.get(key)))
        return lines or ["—"]

    def _format_cache_refresh(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        ordered = ["CLAN_TAGS_CACHE_TTL_SEC", "REFRESH_TIMES", "CLEANUP_AGE_HOURS"]
        lines = [self._format_simple_line(key, entries.get(key)) for key in ordered]
        seen = set(ordered)
        dynamic = [
            key
            for key in entries.keys()
            if key not in seen
            and not _is_secret_key(key)
            and ("TTL" in key or "REFRESH" in key)
        ]
        for key in sorted(dynamic):
            lines.append(self._format_simple_line(key, entries.get(key)))
        return lines or ["—"]

    def _format_watchdog(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        ordered = [
            "WATCHDOG_CHECK_SEC",
            "WATCHDOG_STALL_SEC",
            "WATCHDOG_DISCONNECT_GRACE_SEC",
            "TIMEZONE",
            "PORT",
            "LOG_LEVEL",
        ]
        lines = [self._format_simple_line(key, entries.get(key)) for key in ordered]
        seen = set(ordered)
        dynamic = [
            key
            for key in entries.keys()
            if key not in seen
            and not _is_secret_key(key)
            and (key.startswith("WATCHDOG_") or key in {"TIMEZONE", "PORT", "LOG_LEVEL"})
        ]
        for key in sorted(dynamic):
            lines.append(self._format_simple_line(key, entries.get(key)))
        return lines or ["—"]

    def _format_render(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        keys = [key for key in entries.keys() if key.startswith("RENDER_")]
        if not keys:
            return ["—"]
        return [self._format_simple_line(key, entries.get(key)) for key in sorted(keys)]

    def _format_secrets(self, entries: Dict[str, _EnvEntry]) -> List[str]:
        secrets = [key for key in entries.keys() if _is_secret_key(key)]
        if not secrets:
            return ["—"]
        lines: List[str] = []
        for key in sorted(secrets):
            entry = entries.get(key)
            if entry is None:
                lines.append(f"{key} = —")
                continue
            value = entry.display
            if value == "—":
                lines.append(f"{key} = —")
            else:
                lines.append(f"{key} = {value} (masked)")
        return lines

    def _format_id_lines(self, key: str, ids: Sequence[int]) -> List[str]:
        cleaned: List[int] = []
        seen: Set[int] = set()
        for value in ids:
            try:
                snowflake = int(value)
            except (TypeError, ValueError):
                continue
            if snowflake < 0 or snowflake in seen:
                continue
            seen.add(snowflake)
            cleaned.append(snowflake)

        if not cleaned:
            return [f"{key} = —"]

        label = f"{key}:"
        indent = " " * len(label)
        lines: List[str] = []
        for index, snowflake in enumerate(cleaned):
            resolved = _trim_resolved_label(self._id_resolver.resolve(self.bot, snowflake))
            prefix = label if index == 0 else indent
            lines.append(f"{prefix} {snowflake} → {resolved}")
        return lines

    def _extract_visible_ids(self, key: str, value: object) -> List[int]:
        ids = _extract_ids(key, value)
        return list(ids)

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
