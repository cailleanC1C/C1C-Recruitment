"""Admin command surface for synchronising bot role overwrites."""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import json
import logging
import shlex
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple

import discord
from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import admin_only
from modules.common import runtime as runtime_helpers
from shared.permissions.bot_access_profile import (
    DEFAULT_THREADS_ENABLED,
    build_allow_overwrite,
    build_deny_overwrite,
    serialize_overwrite,
)
from shared.redaction import sanitize_embed

__all__ = ["BotPermissionManager", "BotPermissionCog", "setup"]

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/bot_access_lists.json")
AUDIT_DIR = Path("AUDIT/diagnostics")

TEXTUAL_CHANNEL_TYPES = {
    discord.ChannelType.text,
    discord.ChannelType.news,
    discord.ChannelType.forum,
}


@dataclass(slots=True)
class ChannelPlan:
    channel: discord.abc.GuildChannel
    channel_type: str
    category_label: str
    matched_by: str | None
    intent: str | None
    desired: discord.PermissionOverwrite | None
    existing: discord.PermissionOverwrite | None
    skip_reason: str | None
    needs_change: bool


@dataclass(slots=True)
class ChannelSyncRow:
    channel_id: int
    name: str
    channel_type: str
    category: str
    matched_by: str | None
    prior_state: str
    action: str
    details: str


@dataclass(slots=True)
class SyncReport:
    guild: discord.Guild
    dry: bool
    rows: list[ChannelSyncRow]
    counts: Counter[str]
    matched: int
    processed: int
    csv_path: Path | None
    threads_enabled: bool
    include_voice: bool
    include_stage: bool
    limit: int | None
    updated_threads_default: bool
    error_reasons: Counter[str] = field(default_factory=Counter)


class ChannelOrCategoryConverter(commands.Converter[discord.abc.GuildChannel]):
    """Resolve channels or categories for allow/deny commands."""

    async def convert(
        self, ctx: commands.Context, argument: str
    ) -> discord.abc.GuildChannel:
        guild = getattr(ctx, "guild", None)
        if guild is None:
            raise commands.BadArgument("Guild-only command.")

        try:
            channel = await commands.GuildChannelConverter().convert(ctx, argument)
        except commands.CommandError:
            normalized = argument.strip().strip('"')
            for category in getattr(guild, "categories", []) or []:
                if category.name.lower() == normalized.lower():
                    return category
            raise commands.BadArgument(f"Unknown channel or category: {argument}")
        if isinstance(channel, discord.Thread):
            raise commands.BadArgument("Threads cannot be targeted.")
        return channel


class ListFlags(commands.FlagConverter, delimiter=" "):
    json: bool = commands.flag(default=False, aliases=["j"])


class SyncFlags(commands.FlagConverter, delimiter=" "):
    dry: bool = commands.flag(default=True)
    threads: Optional[str] = None
    include: Optional[str] = None
    limit: Optional[int] = None


class BotAccessStore:
    """Simple JSON-backed persistence for allow/deny lists."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or DEFAULT_CONFIG_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "categories": {"allow": [], "deny": []},
                "channels": {"allow": [], "deny": []},
                "options": {"threads_default": DEFAULT_THREADS_ENABLED},
                "updated_at": None,
            }
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:  # pragma: no cover - defensive fallback
            log.exception("Failed to load bot access list config; using defaults.")
            return {
                "categories": {"allow": [], "deny": []},
                "channels": {"allow": [], "deny": []},
                "options": {"threads_default": DEFAULT_THREADS_ENABLED},
                "updated_at": None,
            }
        return self._normalize(payload)

    def _normalize(self, payload: Mapping[str, object]) -> dict:
        categories = payload.get("categories") or {}
        channels = payload.get("channels") or {}
        options = payload.get("options") or {}
        normalized = {
            "categories": {
                "allow": self._normalize_ids(categories.get("allow")),
                "deny": self._normalize_ids(categories.get("deny")),
            },
            "channels": {
                "allow": self._normalize_ids(channels.get("allow")),
                "deny": self._normalize_ids(channels.get("deny")),
            },
            "options": {
                "threads_default": bool(
                    options.get("threads_default", DEFAULT_THREADS_ENABLED)
                ),
            },
            "updated_at": payload.get("updated_at"),
        }
        return normalized

    @staticmethod
    def _normalize_ids(raw: object) -> list[int]:
        items: set[int] = set()
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                try:
                    items.add(int(item))
                except (TypeError, ValueError):
                    continue
        return sorted(items)

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self._data))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @staticmethod
    def _now_timestamp() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def _set_updated(self) -> None:
        self._data["updated_at"] = self._now_timestamp()

    def add_ids(
        self,
        scope: str,
        bucket: str,
        ids: Iterable[int],
    ) -> list[int]:
        target_list = self._data[scope][bucket]
        added: list[int] = []
        for item in sorted({int(x) for x in ids}):
            if item not in target_list:
                target_list.append(item)
                added.append(item)
        if added:
            target_list.sort()
            self._set_updated()
            self.save()
        return added

    def remove_from_bucket(
        self, scope: str, bucket: str, ids: Iterable[int]
    ) -> list[int]:
        target_list = self._data[scope][bucket]
        removed: list[int] = []
        remaining: list[int] = []
        ids_set = {int(x) for x in ids}
        for item in target_list:
            if item in ids_set:
                removed.append(item)
            else:
                remaining.append(item)
        if removed:
            target_list[:] = sorted(remaining)
            self._set_updated()
            self.save()
        return sorted(removed)

    def remove_ids(self, scope: str, ids: Iterable[int]) -> list[int]:
        bucket_map = self._data[scope]
        removed: set[int] = set()
        for bucket in ("allow", "deny"):
            source = bucket_map[bucket]
            before = set(source)
            source[:] = [item for item in source if item not in ids]
            removed.update(before.difference(source))
        if removed:
            self._set_updated()
            self.save()
        return sorted(removed)

    def set_threads_default(self, enabled: bool) -> None:
        if self._data["options"].get("threads_default") == enabled:
            return
        self._data["options"]["threads_default"] = enabled
        self._set_updated()
        self.save()

    def threads_default(self) -> bool:
        return bool(self._data["options"].get("threads_default", DEFAULT_THREADS_ENABLED))


class BotPermissionManager:
    """Central orchestration for sync commands and watcher helpers."""

    _attribute_name = "_bot_permission_manager"

    def __init__(
        self,
        bot: commands.Bot,
        store: BotAccessStore | None = None,
    ) -> None:
        self.bot = bot
        self.store = store or BotAccessStore()
        self._lock = asyncio.Lock()

    @classmethod
    def for_bot(
        cls, bot: commands.Bot, store: BotAccessStore | None = None
    ) -> "BotPermissionManager":
        manager = getattr(bot, cls._attribute_name, None)
        if manager is None:
            manager = cls(bot, store=store)
            setattr(bot, cls._attribute_name, manager)
        return manager

    @staticmethod
    def _category_label(channel: discord.abc.GuildChannel) -> str:
        category = getattr(channel, "category", None)
        if category is None:
            return "—"
        name = getattr(category, "name", None) or "Unnamed"
        return f"{name} ({category.id})"

    @staticmethod
    def _channel_type_name(channel: discord.abc.GuildChannel) -> str:
        channel_type = getattr(channel, "type", None)
        if isinstance(channel_type, discord.ChannelType):
            return channel_type.name
        return str(channel_type)

    @staticmethod
    def _resolve_role(guild: discord.Guild) -> discord.Role:
        for role in getattr(guild, "roles", []) or []:
            name = getattr(role, "name", "")
            if isinstance(name, str) and name.lower() == "bot":
                return role
        raise commands.CommandError(
            "Bot role named 'bot' not found; cannot manage overwrites."
        )

    @staticmethod
    def _channel_in_scope(
        channel: discord.abc.GuildChannel,
        *,
        include_voice: bool,
        include_stage: bool,
    ) -> bool:
        channel_type = getattr(channel, "type", None)
        if channel_type == discord.ChannelType.category:
            return True
        if channel_type in TEXTUAL_CHANNEL_TYPES:
            return True
        if channel_type == discord.ChannelType.voice:
            return include_voice
        if channel_type == discord.ChannelType.stage_voice:
            return include_stage
        return False

    @staticmethod
    def _classify_channel(
        channel: discord.abc.GuildChannel,
        *,
        allow_categories: set[int],
        allow_channels: set[int],
        deny_categories: set[int],
        deny_channels: set[int],
    ) -> tuple[str | None, str | None]:
        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return (None, None)
        if getattr(channel, "type", None) == discord.ChannelType.category:
            if channel_id in deny_categories:
                return ("deny", "category-deny")
            if channel_id in allow_categories:
                return ("allow", "category-allow")
            return (None, None)
        if channel_id in deny_channels:
            return ("deny", "channel-deny")
        category_id = getattr(channel, "category_id", None)
        if category_id in deny_categories:
            return ("deny", "category-deny")
        if channel_id in allow_channels:
            return ("allow", "channel-allow")
        if category_id in allow_categories:
            return ("allow", "category-allow")
        return (None, None)

    @staticmethod
    def _existing_overwrite(
        channel: discord.abc.GuildChannel,
        role: discord.Role,
    ) -> discord.PermissionOverwrite | None:
        overwrites = getattr(channel, "overwrites", None)
        if isinstance(overwrites, Mapping) and role in overwrites:
            return overwrites[role]
        try:
            overwrite = channel.overwrites_for(role)
        except Exception:  # pragma: no cover - discord.py guard
            return None
        if overwrite.is_empty():
            return None
        return overwrite

    @staticmethod
    def _summarize_exception(exc: Exception) -> str:
        message = str(exc).strip()
        if not message:
            message = exc.__class__.__name__
        sanitized = " ".join(message.split())
        return sanitized[:200]

    def _build_plan(
        self,
        channel: discord.abc.GuildChannel,
        *,
        role: discord.Role,
        allow_categories: set[int],
        allow_channels: set[int],
        deny_categories: set[int],
        deny_channels: set[int],
        threads_enabled: bool,
        include_voice: bool,
        include_stage: bool,
    ) -> ChannelPlan:
        channel_type_name = self._channel_type_name(channel)
        category_label = self._category_label(channel)
        if not self._channel_in_scope(
            channel, include_voice=include_voice, include_stage=include_stage
        ):
            return ChannelPlan(
                channel=channel,
                channel_type=channel_type_name,
                category_label=category_label,
                matched_by=None,
                intent=None,
                desired=None,
                existing=None,
                skip_reason="type-skip",
                needs_change=False,
            )
        intent, matched_by = self._classify_channel(
            channel,
            allow_categories=allow_categories,
            allow_channels=allow_channels,
            deny_categories=deny_categories,
            deny_channels=deny_channels,
        )
        if intent is None:
            return ChannelPlan(
                channel=channel,
                channel_type=channel_type_name,
                category_label=category_label,
                matched_by=None,
                intent=None,
                desired=None,
                existing=None,
                skip_reason=None,
                needs_change=False,
            )
        existing = self._existing_overwrite(channel, role)
        if intent == "allow" and existing is not None:
            if getattr(existing, "view_channel", None) is False:
                return ChannelPlan(
                    channel=channel,
                    channel_type=channel_type_name,
                    category_label=category_label,
                    matched_by=matched_by,
                    intent=intent,
                    desired=None,
                    existing=existing,
                    skip_reason="manual-view-deny",
                    needs_change=False,
                )
        desired = (
            build_allow_overwrite(threads_enabled=threads_enabled)
            if intent == "allow"
            else build_deny_overwrite()
        )
        needs_change = existing is None or existing != desired
        return ChannelPlan(
            channel=channel,
            channel_type=channel_type_name,
            category_label=category_label,
            matched_by=matched_by,
            intent=intent,
            desired=desired,
            existing=existing,
            skip_reason=None,
            needs_change=needs_change,
        )

    async def apply_single(
        self,
        channel: discord.abc.GuildChannel,
        *,
        include_voice: bool = False,
        include_stage: bool = False,
        reason: str | None = None,
    ) -> Tuple[str, ChannelPlan]:
        guild = getattr(channel, "guild", None)
        if guild is None:
            return (
                "skip-no-guild",
                ChannelPlan(
                    channel=channel,
                    channel_type=self._channel_type_name(channel),
                    category_label=self._category_label(channel),
                    matched_by=None,
                    intent=None,
                    desired=None,
                    existing=None,
                    skip_reason="no-guild",
                    needs_change=False,
                ),
            )
        async with self._lock:
            role = self._resolve_role(guild)
            snapshot = self.store.snapshot()
            threads_enabled = self.store.threads_default()
            allow_categories = set(snapshot["categories"]["allow"])
            allow_channels = set(snapshot["channels"]["allow"])
            deny_categories = set(snapshot["categories"]["deny"])
            deny_channels = set(snapshot["channels"]["deny"])
            plan = self._build_plan(
                channel,
                role=role,
                allow_categories=allow_categories,
                allow_channels=allow_channels,
                deny_categories=deny_categories,
                deny_channels=deny_channels,
                threads_enabled=threads_enabled,
                include_voice=include_voice,
                include_stage=include_stage,
            )
            role_ref = role
        if plan.intent is None:
            return ("skip-unlisted", plan)
        if plan.skip_reason == "manual-view-deny":
            return ("skip-manual", plan)
        if plan.skip_reason:
            return ("skip", plan)
        if not plan.needs_change or plan.desired is None:
            return ("noop", plan)
        try:
            await channel.set_permissions(
                role_ref,
                overwrite=plan.desired,
                reason=reason,
            )
        except Exception:  # pragma: no cover - network failure
            log.warning(
                "Failed to update permissions for %s", channel, exc_info=True
            )
            return ("error", plan)
        return ("applied", plan)

    async def sync(
        self,
        guild: discord.Guild,
        *,
        dry: bool,
        threads_enabled: bool | None = None,
        include_voice: bool = False,
        include_stage: bool = False,
        limit: int | None = None,
        write_csv: bool = True,
        persist_threads: bool = False,
    ) -> SyncReport:
        async with self._lock:
            role = self._resolve_role(guild)
            snapshot = self.store.snapshot()
            allow_categories = set(snapshot["categories"]["allow"])
            allow_channels = set(snapshot["channels"]["allow"])
            deny_categories = set(snapshot["categories"]["deny"])
            deny_channels = set(snapshot["channels"]["deny"])
            threads_default = self.store.threads_default()
            threads_flag = (
                threads_enabled if threads_enabled is not None else threads_default
            )
            channels = list(getattr(guild, "channels", []) or [])
            plans = [
                self._build_plan(
                    channel,
                    role=role,
                    allow_categories=allow_categories,
                    allow_channels=allow_channels,
                    deny_categories=deny_categories,
                    deny_channels=deny_channels,
                    threads_enabled=threads_flag,
                    include_voice=include_voice,
                    include_stage=include_stage,
                )
                for channel in channels
            ]
            role_ref = role
        matched_plans = [plan for plan in plans if plan.intent is not None]
        rows: list[ChannelSyncRow] = []
        counts: Counter[str] = Counter()
        processed = 0
        limit_value = limit if isinstance(limit, int) and limit > 0 else None
        error_reasons: Counter[str] = Counter()
        for plan in matched_plans:
            channel = plan.channel
            prior = serialize_overwrite(plan.existing)
            if plan.skip_reason == "manual-view-deny":
                rows.append(
                    ChannelSyncRow(
                        channel_id=getattr(channel, "id", 0),
                        name=getattr(channel, "name", "Unnamed"),
                        channel_type=plan.channel_type,
                        category=plan.category_label,
                        matched_by=plan.matched_by,
                        prior_state=prior,
                        action="skip-manual-deny",
                        details="existing view_channel deny",
                    )
                )
                counts["skip_manual_deny"] += 1
                continue
            if plan.skip_reason is not None:
                continue
            channel_id = getattr(channel, "id", 0)
            name = getattr(channel, "name", "Unnamed")
            if not plan.needs_change or plan.desired is None:
                rows.append(
                    ChannelSyncRow(
                        channel_id=channel_id,
                        name=name,
                        channel_type=plan.channel_type,
                        category=plan.category_label,
                        matched_by=plan.matched_by,
                        prior_state=prior,
                        action="noop",
                        details="no changes required",
                    )
                )
                counts["noop"] += 1
                continue
            if limit_value is not None and processed >= limit_value:
                rows.append(
                    ChannelSyncRow(
                        channel_id=channel_id,
                        name=name,
                        channel_type=plan.channel_type,
                        category=plan.category_label,
                        matched_by=plan.matched_by,
                        prior_state=prior,
                        action="skip-limit",
                        details=f"limit {limit_value} reached",
                    )
                )
                counts["skip_limit"] += 1
                continue
            processed += 1
            if dry:
                action = "plan-create" if plan.existing is None else "plan-update"
                details = (
                    "would create overwrite"
                    if plan.existing is None
                    else "would update overwrite"
                )
                rows.append(
                    ChannelSyncRow(
                        channel_id=channel_id,
                        name=name,
                        channel_type=plan.channel_type,
                        category=plan.category_label,
                        matched_by=plan.matched_by,
                        prior_state=prior,
                        action=action,
                        details=details,
                    )
                )
                counts[action] += 1
            else:
                try:
                    await plan.channel.set_permissions(
                        role_ref,
                        overwrite=plan.desired,
                        reason="bot role sync",
                    )
                except Exception as exc:  # pragma: no cover - discord.py failure
                    reason = self._summarize_exception(exc)
                    log.warning(
                        "Failed to apply overwrite for channel %s",
                        plan.channel,
                        exc_info=True,
                        extra={"error_reason": reason},
                    )
                    rows.append(
                        ChannelSyncRow(
                            channel_id=channel_id,
                            name=name,
                            channel_type=plan.channel_type,
                            category=plan.category_label,
                            matched_by=plan.matched_by,
                            prior_state=prior,
                            action="error",
                            details=f"exception applying overwrite: {reason}",
                        )
                    )
                    counts["error"] += 1
                    error_reasons[reason] += 1
                    continue
                action = "created" if plan.existing is None else "updated"
                details = (
                    "created overwrite"
                    if plan.existing is None
                    else "updated overwrite"
                )
                rows.append(
                    ChannelSyncRow(
                        channel_id=channel_id,
                        name=name,
                        channel_type=plan.channel_type,
                        category=plan.category_label,
                        matched_by=plan.matched_by,
                        prior_state=prior,
                        action=action,
                        details=details,
                    )
                )
                counts[action] += 1
        csv_path: Path | None = None
        if write_csv:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M")
            filename = f"{guild.id}-{timestamp}-bot_sync.csv"
            csv_path = AUDIT_DIR / filename
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "channel_id",
                        "name",
                        "type",
                        "category",
                        "matched_by",
                        "prior_state",
                        "action",
                        "details",
                    ]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row.channel_id,
                            row.name,
                            row.channel_type,
                            row.category,
                            row.matched_by or "",
                            row.prior_state,
                            row.action,
                            row.details,
                        ]
                    )
        updated_threads_default = False
        if not dry and persist_threads and threads_enabled is not None:
            self.store.set_threads_default(threads_flag)
            updated_threads_default = True
        return SyncReport(
            guild=guild,
            dry=dry,
            rows=rows,
            counts=counts,
            matched=len(matched_plans),
            processed=processed,
            csv_path=csv_path,
            threads_enabled=threads_flag,
            include_voice=include_voice,
            include_stage=include_stage,
            limit=limit_value,
            updated_threads_default=updated_threads_default,
            error_reasons=error_reasons,
        )

    @staticmethod
    def _parse_boolean_flag(raw: Optional[str], *, label: str) -> Optional[bool]:
        if raw is None:
            return None
        normalized = raw.strip().lower()
        if normalized in {"on", "true", "yes", "1"}:
            return True
        if normalized in {"off", "false", "no", "0"}:
            return False
        raise commands.BadArgument(f"Invalid value for --{label}: {raw}")


class BotPermissionCog(commands.Cog):
    """Expose admin commands for the bot permission manager."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = BotPermissionManager.for_bot(bot)

    @staticmethod
    def _chunk_lines(lines: Sequence[str], limit: int = 900) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in lines:
            text = line.rstrip() or "—"
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

    def _add_embed_section(
        self, embed: discord.Embed, name: str, entries: Sequence[str]
    ) -> None:
        normalized = [entry for entry in entries if entry]
        if not normalized:
            normalized = ["—"]
        chunks = self._chunk_lines(normalized)
        for index, chunk in enumerate(chunks):
            label = name if index == 0 else f"{name} (cont.)"
            embed.add_field(name=label, value=chunk, inline=False)

    @staticmethod
    def _tokenize_targets(raw: str) -> list[str]:
        try:
            return shlex.split(raw)
        except ValueError as exc:
            raise commands.BadArgument(f"Invalid target list: {exc}") from exc

    async def _resolve_targets(
        self, ctx: commands.Context, raw: str
    ) -> list[discord.abc.GuildChannel]:
        tokens = self._tokenize_targets(raw)
        if not tokens:
            return []
        converter = ChannelOrCategoryConverter()
        resolved: list[discord.abc.GuildChannel] = []
        seen: set[int] = set()
        for token in tokens:
            channel = await converter.convert(ctx, token)
            identifier = getattr(channel, "id", None)
            if identifier is None or identifier in seen:
                continue
            seen.add(int(identifier))
            resolved.append(channel)
        return resolved

    @staticmethod
    def _format_category_entry(guild: discord.Guild, category_id: int) -> str:
        channel = guild.get_channel(category_id)
        if isinstance(channel, discord.CategoryChannel):
            return f"• {channel.name} — {category_id}"
        return f"• ⚠️ Missing category — {category_id}"

    @staticmethod
    def _format_channel_entry(guild: discord.Guild, channel_id: int) -> str:
        channel = guild.get_channel(channel_id)
        if channel is None:
            return f"• ⚠️ Missing channel — {channel_id}"
        name = getattr(channel, "name", str(channel_id))
        prefix = "#" if getattr(channel, "type", None) in TEXTUAL_CHANNEL_TYPES else "•"
        return f"{prefix} {name} — {channel_id}"

    async def _send_snapshot_json(self, ctx: commands.Context, snapshot: dict) -> None:
        payload = json.dumps(snapshot, indent=2, sort_keys=True)
        chunks: list[str] = []
        chunk: list[str] = []
        current_len = 0
        for line in payload.splitlines():
            line_len = len(line) + 1
            if current_len + line_len > 1900 and chunk:
                chunks.append("\n".join(chunk))
                chunk = []
                current_len = 0
            chunk.append(line)
            current_len += line_len
        if chunk:
            chunks.append("\n".join(chunk))
        for part in chunks:
            await ctx.send(f"```json\n{part}\n```")

    def _format_mutation_message(
        self,
        guild: discord.Guild,
        *,
        header: str,
        categories: Sequence[int],
        channels: Sequence[int],
        removed_from: str | None = None,
    ) -> str:
        lines = [header]
        if categories:
            lines.append("")
            lines.append(f"🗂️ Categories ({len(categories)})")
            lines.extend(
                self._format_category_entry(guild, category_id) for category_id in categories
            )
        if channels:
            lines.append("")
            lines.append(f"📺 Channels ({len(channels)})")
            lines.extend(
                self._format_channel_entry(guild, channel_id) for channel_id in channels
            )
        if not categories and not channels:
            lines.append("No changes.")
        if removed_from:
            lines.append("")
            lines.append(removed_from)
        return "\n".join(lines)

    def _format_sync_summary(
        self, report: SyncReport, *, preview: bool = False
    ) -> str:
        header = "🔍 Bot role sync preview" if preview or report.dry else "✅ Bot role sync complete"
        lines = [
            f"{header} — {report.guild.name} ({report.guild.id})",
            f"• Matched channels: {report.matched}",
            f"• Processed: {report.processed}",
            f"• Threads: {'on' if report.threads_enabled else 'off'}",
            f"• Include voice: {'yes' if report.include_voice else 'no'}",
            f"• Include stage: {'yes' if report.include_stage else 'no'}",
        ]
        if report.limit is not None:
            lines.append(f"• Limit: {report.limit}")
        if report.dry:
            planned = report.counts.get("plan-create", 0) + report.counts.get(
                "plan-update", 0
            )
            lines.append(f"• Planned overwrites: {planned}")
        else:
            applied = report.counts.get("created", 0) + report.counts.get(
                "updated", 0
            )
            lines.append(f"• Applied overwrites: {applied}")
            errors = report.counts.get("error", 0)
            if errors:
                lines.append(f"• Errors: {errors}")
                if report.error_reasons:
                    lines.append("• Error details:")
                    for reason, count in report.error_reasons.most_common(3):
                        lines.append(f"  • {count}× {reason}")
                    if len(report.error_reasons) > 3:
                        lines.append(
                            "  • … additional error types logged"
                        )
        if report.counts.get("noop"):
            lines.append(f"• No-ops: {report.counts['noop']}")
        if report.counts.get("skip_manual_deny"):
            lines.append(
                f"• Skipped manual denies: {report.counts['skip_manual_deny']}"
            )
        if report.counts.get("skip_limit"):
            lines.append(f"• Limit skips: {report.counts['skip_limit']}")
        if report.csv_path is not None:
            lines.append(f"• Audit CSV: {report.csv_path}")
        if report.updated_threads_default:
            lines.append(
                f"• Threads default persisted: {'on' if report.threads_enabled else 'off'}"
            )
        return "\n".join(lines)

    @tier("admin")
    @commands.group(
        name="perm",
        invoke_without_command=True,
        help="Manages bot allow/deny configuration.",
        brief="Manages bot allow/deny configuration.",
    )
    @admin_only()
    async def perm_group(self, ctx: commands.Context) -> None:
        await ctx.reply(
            "Use `!perm bot list` to inspect or `!perm bot sync` to preview changes.",
            mention_author=False,
        )

    @tier("admin")
    @perm_group.group(
        name="bot",
        invoke_without_command=True,
        help="Manages bot allow/deny subcommands.",
        brief="Manages bot allow/deny subcommands.",
    )
    @admin_only()
    async def perm_bot(self, ctx: commands.Context) -> None:
        await ctx.reply(
            "Available subcommands: list, allow, deny, remove, sync.",
            mention_author=False,
        )
    _extras = getattr(perm_bot, "extras", None)
    if isinstance(_extras, dict):
        _extras.setdefault("hide_in_help", True)
    else:  # pragma: no cover - defensive fallback
        perm_bot.extras = {"hide_in_help": True}

    @tier("admin")
    @help_metadata(function_group="operational", section="permissions", access_tier="admin")
    @perm_bot.command(
        name="list",
        help="Shows the current allow/deny configuration.",
        brief="Shows the current allow/deny configuration.",
    )
    @admin_only()
    async def perm_bot_list(self, ctx: commands.Context, *, flags: ListFlags) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild only.", mention_author=False)
            return
        snapshot = self.manager.store.snapshot()
        categories_allow = snapshot["categories"]["allow"]
        categories_deny = snapshot["categories"]["deny"]
        channels_allow = snapshot["channels"]["allow"]
        channels_deny = snapshot["channels"]["deny"]
        updated = snapshot.get("updated_at") or "never"
        totals_line = " · ".join(
            [
                f"allowed categories: {len(categories_allow)}",
                f"allowed channels: {len(channels_allow)}",
                f"denied categories: {len(categories_deny)}",
                f"denied channels: {len(channels_deny)}",
            ]
        )
        embed = discord.Embed(
            title=f"{runtime_helpers.get_bot_name()} · bot access",
            description=totals_line,
            colour=discord.Colour.blurple(),
        )
        embed.set_author(name=guild.name)
        embed.set_footer(text=f"Last updated: {updated}")

        if isinstance(updated, str) and updated not in {"", "never"}:
            try:
                parsed = dt.datetime.fromisoformat(updated)
            except ValueError:
                parsed = None
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                embed.timestamp = parsed

        self._add_embed_section(
            embed,
            "🟩 Allowed Categories",
            [
                self._format_category_entry(guild, category_id)
                for category_id in categories_allow
            ],
        )
        self._add_embed_section(
            embed,
            "🟩 Allowed Channels",
            [
                self._format_channel_entry(guild, channel_id)
                for channel_id in channels_allow
            ],
        )
        self._add_embed_section(
            embed,
            "🟥 Denied Categories",
            [
                self._format_category_entry(guild, category_id)
                for category_id in categories_deny
            ],
        )
        self._add_embed_section(
            embed,
            "🟥 Denied Channels",
            [
                self._format_channel_entry(guild, channel_id)
                for channel_id in channels_deny
            ],
        )

        await ctx.reply(embed=sanitize_embed(embed), mention_author=False)
        if flags.json:
            await self._send_snapshot_json(ctx, snapshot)

    @tier("admin")
    @help_metadata(function_group="operational", section="permissions", access_tier="admin")
    @perm_bot.command(
        name="allow",
        help="Adds channels or categories to the allow list.",
        brief="Adds channels or categories to the allow list.",
    )
    @admin_only()
    async def perm_bot_allow(self, ctx: commands.Context, *, targets: str) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild only.", mention_author=False)
            return
        resolved = await self._resolve_targets(ctx, targets)
        if not resolved:
            await ctx.reply("Provide at least one channel or category.", mention_author=False)
            return
        category_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) == discord.ChannelType.category
        }
        channel_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) != discord.ChannelType.category
        }
        added_categories = self.manager.store.add_ids(
            "categories", "allow", category_ids
        )
        added_channels = self.manager.store.add_ids("channels", "allow", channel_ids)
        removed_note_parts: list[str] = []
        if category_ids:
            removed = self.manager.store.remove_from_bucket(
                "categories", "deny", category_ids
            )
            if removed:
                removed_note_parts.append(
                    f"Removed {len(removed)} category entries from deny list."
                )
        if channel_ids:
            removed = self.manager.store.remove_from_bucket(
                "channels", "deny", channel_ids
            )
            if removed:
                removed_note_parts.append(
                    f"Removed {len(removed)} channel entries from deny list."
                )
        message = self._format_mutation_message(
            guild,
            header="🟩 Allow list updated",
            categories=added_categories,
            channels=added_channels,
            removed_from=" ".join(removed_note_parts) if removed_note_parts else None,
        )
        await ctx.reply(message, mention_author=False)

    @tier("admin")
    @help_metadata(function_group="operational", section="permissions", access_tier="admin")
    @perm_bot.command(
        name="deny",
        help="Adds channels or categories to the deny list.",
        brief="Adds channels or categories to the deny list.",
    )
    @admin_only()
    async def perm_bot_deny(self, ctx: commands.Context, *, targets: str) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild only.", mention_author=False)
            return
        resolved = await self._resolve_targets(ctx, targets)
        if not resolved:
            await ctx.reply("Provide at least one channel or category.", mention_author=False)
            return
        category_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) == discord.ChannelType.category
        }
        channel_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) != discord.ChannelType.category
        }
        added_categories = self.manager.store.add_ids(
            "categories", "deny", category_ids
        )
        added_channels = self.manager.store.add_ids("channels", "deny", channel_ids)
        removed_note_parts: list[str] = []
        if category_ids:
            removed = self.manager.store.remove_from_bucket(
                "categories", "allow", category_ids
            )
            if removed:
                removed_note_parts.append(
                    f"Removed {len(removed)} category entries from allow list."
                )
        if channel_ids:
            removed = self.manager.store.remove_from_bucket(
                "channels", "allow", channel_ids
            )
            if removed:
                removed_note_parts.append(
                    f"Removed {len(removed)} channel entries from allow list."
                )
        message = self._format_mutation_message(
            guild,
            header="🟥 Deny list updated",
            categories=added_categories,
            channels=added_channels,
            removed_from=" ".join(removed_note_parts) if removed_note_parts else None,
        )
        await ctx.reply(message, mention_author=False)

    @tier("admin")
    @help_metadata(function_group="operational", section="permissions", access_tier="admin")
    @perm_bot.command(
        name="remove",
        help="Removes channels or categories from allow/deny lists.",
        brief="Removes channels or categories from allow/deny lists.",
    )
    @admin_only()
    async def perm_bot_remove(self, ctx: commands.Context, *, targets: str) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild only.", mention_author=False)
            return
        resolved = await self._resolve_targets(ctx, targets)
        if not resolved:
            await ctx.reply("Provide at least one channel or category.", mention_author=False)
            return
        category_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) == discord.ChannelType.category
        }
        channel_ids = {
            int(getattr(target, "id"))
            for target in resolved
            if getattr(target, "type", None) != discord.ChannelType.category
        }
        removed_categories = self.manager.store.remove_ids("categories", category_ids)
        removed_channels = self.manager.store.remove_ids("channels", channel_ids)
        message = self._format_mutation_message(
            guild,
            header="🗑️ Entries removed",
            categories=removed_categories,
            channels=removed_channels,
        )
        await ctx.reply(message, mention_author=False)

    @tier("admin")
    @help_metadata(function_group="operational", section="permissions", access_tier="admin")
    @perm_bot.command(
        name="sync",
        help="Applies allow/deny changes to Discord overwrites.",
        brief="Applies allow/deny changes to Discord overwrites.",
    )
    @admin_only()
    async def perm_bot_sync(self, ctx: commands.Context, *, flags: SyncFlags) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild only.", mention_author=False)
            return
        threads_flag = BotPermissionManager._parse_boolean_flag(
            flags.threads, label="threads"
        )
        include_tokens = set()
        if flags.include:
            for token in flags.include.replace(",", " ").split():
                normalized = token.strip().lower()
                if normalized:
                    include_tokens.add(normalized)
        include_voice = "voice" in include_tokens
        include_stage = "stage" in include_tokens
        limit_value = None
        if flags.limit is not None:
            if flags.limit <= 0:
                raise commands.BadArgument("--limit must be positive")
            limit_value = flags.limit
        if flags.dry:
            report = await self.manager.sync(
                guild,
                dry=True,
                threads_enabled=threads_flag,
                include_voice=include_voice,
                include_stage=include_stage,
                limit=limit_value,
                write_csv=True,
            )
            await ctx.reply(
                self._format_sync_summary(report, preview=True),
                mention_author=False,
            )
            return

        preview = await self.manager.sync(
            guild,
            dry=True,
            threads_enabled=threads_flag,
            include_voice=include_voice,
            include_stage=include_stage,
            limit=limit_value,
            write_csv=False,
        )
        await ctx.reply(
            self._format_sync_summary(preview, preview=True),
            mention_author=False,
        )
        await ctx.send(
            "⚠️ Live sync requested. Type `confirm` in the next 45 seconds to proceed.",
        )

        def check(message: discord.Message) -> bool:
            return (
                message.author == ctx.author
                and message.channel == ctx.channel
                and message.content.strip().lower() == "confirm"
            )

        try:
            await self.bot.wait_for("message", check=check, timeout=45.0)
        except asyncio.TimeoutError:
            await ctx.send("⏱️ Sync cancelled (timeout).")
            return

        report = await self.manager.sync(
            guild,
            dry=False,
            threads_enabled=threads_flag,
            include_voice=include_voice,
            include_stage=include_stage,
            limit=limit_value,
            write_csv=True,
            persist_threads=True,
        )
        await ctx.reply(
            self._format_sync_summary(report, preview=False),
            mention_author=False,
        )
        applied = report.counts.get("created", 0) + report.counts.get("updated", 0)
        errors = report.counts.get("error", 0)
        error_suffix = ""
        if errors and report.error_reasons:
            top_reasons = ", ".join(
                f"{count}× {reason}"
                for reason, count in report.error_reasons.most_common(2)
            )
            error_suffix = f" [{top_reasons}]"
        await runtime_helpers.send_log_message(
            "🔐 Bot permission sync applied: "
            f"{applied} overwrites, errors={errors}, "
            f"threads={'on' if report.threads_enabled else 'off'}{error_suffix}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotPermissionCog(bot))
