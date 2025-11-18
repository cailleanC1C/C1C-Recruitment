"""Discord cog implementing the Shard & Mercy tracker commands."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import discord
from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from modules.common import feature_flags
from shared import config as shared_config
from shared.config import get_admin_role_ids
from shared.logfmt import user_label

from .data import (
    ShardRecord,
    ShardSheetStore,
    ShardTrackerConfigError,
    ShardTrackerSheetError,
)
from .mercy import MERCY_PROFILES, MercyProfile, MercyState, calculate_mercy
from .threads import ShardThreadRouter
from .views import (
    ShardDisplay,
    ShardTrackerController,
    ShardTrackerView,
    build_detail_embed,
    build_summary_embed,
)
from modules.common import runtime

log = logging.getLogger("c1c.shards.cog")


@dataclass(frozen=True)
class ShardKind:
    key: str
    label: str
    stash_field: str
    mercy_field: str
    mercy_profile: MercyProfile
    timestamp_field: str


SHARD_KINDS: Dict[str, ShardKind] = {
    "ancient": ShardKind(
        key="ancient",
        label="Ancient",
        stash_field="ancients_owned",
        mercy_field="ancients_since_lego",
        mercy_profile=MERCY_PROFILES["ancient"],
        timestamp_field="last_ancient_lego_iso",
    ),
    "void": ShardKind(
        key="void",
        label="Void",
        stash_field="voids_owned",
        mercy_field="voids_since_lego",
        mercy_profile=MERCY_PROFILES["void"],
        timestamp_field="last_void_lego_iso",
    ),
    "sacred": ShardKind(
        key="sacred",
        label="Sacred",
        stash_field="sacreds_owned",
        mercy_field="sacreds_since_lego",
        mercy_profile=MERCY_PROFILES["sacred"],
        timestamp_field="last_sacred_lego_iso",
    ),
    "primal": ShardKind(
        key="primal",
        label="Primal",
        stash_field="primals_owned",
        mercy_field="primals_since_lego",
        mercy_profile=MERCY_PROFILES["primal"],
        timestamp_field="last_primal_lego_iso",
    ),
}

_TYPE_ALIASES = {
    "a": "ancient",
    "anc": "ancient",
    "ancients": "ancient",
    "v": "void",
    "voids": "void",
    "s": "sacred",
    "sac": "sacred",
    "sacreds": "sacred",
    "p": "primal",
    "primals": "primal",
    "myth": "mythic",
    "mythical": "mythic",
}

_FEATURE_TOGGLE_KEYS = ("shardtracker", "shard_tracker")


class ShardTrackerCog(commands.Cog, ShardTrackerController):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.store = ShardSheetStore()
        self.threads = ShardThreadRouter(bot)
        self._locks: Dict[int, asyncio.Lock] = {}

    # === Commands ===

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help=(
            "Shard dashboard with stash counts and mercy chance. Only runs in the Shards & Mercy channel; "
            "creates your personal thread when needed."
        ),
        usage="!shards [type]",
    )
    @commands.group(name="shards", invoke_without_command=True)
    async def shards(self, ctx: commands.Context, *, shard_type: str | None = None) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_shards(ctx, shard_type)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help="Set the shard stash count for a specific type (non-negative integers only).",
        usage="!shards set <type> <count>",
    )
    @shards.command(name="set")
    async def shards_set(self, ctx: commands.Context, shard_type: str, count: int) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_stash_set(ctx, shard_type, count)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help=(
            "Show mercy counters for all shard types inside your personal thread in the Shards & Mercy channel."
        ),
        usage="!mercy [type]",
    )
    @commands.group(name="mercy", invoke_without_command=True)
    async def mercy(self, ctx: commands.Context, *, shard_type: str | None = None) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_shards(ctx, shard_type)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help="Override a mercy counter. Accepts `mythic` to target the primal mythic pity.",
        usage="!mercy set <type> <count>",
    )
    @mercy.command(name="set")
    async def mercy_set(self, ctx: commands.Context, shard_type: str, count: int) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_mercy_set(ctx, shard_type, count)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help=(
            "Log a legendary pull for a shard type. Accepts the number of shards you pulled after the LEGO before logging."
        ),
        usage="!lego <type> [after_count]",
    )
    @commands.command(name="lego")
    async def log_lego(
        self, ctx: commands.Context, shard_type: str, after_count: int = 0
    ) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_lego(ctx, shard_type, after_count)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help=(
            "Log a primal mythic pull. Accepts how many shards you pulled after the mythic before logging."
        ),
        usage="!mythic primal [after_count]",
    )
    @commands.group(name="mythic", aliases=["mythical"], invoke_without_command=True)
    async def mythic(self, ctx: commands.Context) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await ctx.reply("Specify the shard type: `!mythic primal <after_count>`.", mention_author=False)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        help="Log a primal mythic drop and reset the primal counters (channel + thread restricted).",
        usage="!mythic primal [after_count]",
    )
    @mythic.command(name="primal")
    async def mythic_primal(self, ctx: commands.Context, after_count: int = 0) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_mythic(ctx, after_count)

    # === Button controller ===

    async def handle_button_interaction(
        self,
        *,
        interaction: discord.Interaction,
        shard_key: str,
        action: str,
    ) -> None:
        if not self._feature_enabled():
            await interaction.response.send_message(
                self._feature_disabled_message(), ephemeral=True
            )
            return
        ctx_author = interaction.user
        guild = getattr(interaction.guild, "id", None)
        if guild is None:
            await interaction.response.send_message(
                "Shard tracker is only available in guild channels.", ephemeral=True
            )
            return
        async with self._user_lock(ctx_author.id):
            try:
                config = await self.store.get_config()
            except ShardTrackerConfigError as exc:
                await interaction.response.send_message(
                    self._config_error_message(str(exc)),
                    ephemeral=True,
                )
                await self._notify_admins(str(exc))
                return
            try:
                record = await self.store.load_record(ctx_author.id, ctx_author.display_name or ctx_author.name)
            except ShardTrackerSheetError as exc:
                await interaction.response.send_message(
                    "Shard tracker sheet misconfigured. Please contact an admin.",
                    ephemeral=True,
                )
                await self._notify_admins(str(exc))
                return
            kind = self._resolve_kind(shard_key)
            if kind is None:
                await interaction.response.send_message(
                    "Unknown shard type for this button.", ephemeral=True
                )
                return
            self._apply_button_action(record, kind, action)
            record.snapshot_name(ctx_author.display_name or ctx_author.name)
            await self.store.save_record(config, record)
            embed, view = self._build_summary_payload(ctx_author, record, interaction.channel)
            await interaction.response.edit_message(embed=embed, view=view)
            await self._log_action(
                "button",
                ctx_author,
                interaction.channel,
                f"{action} {kind.label}",
            )

    # === Internal helpers ===

    def _feature_disabled_message(self) -> str:
        return "Shard & Mercy tracking is currently disabled. Please check back later."

    async def _ensure_feature_enabled(self, ctx: commands.Context) -> bool:
        if self._feature_enabled():
            return True
        await ctx.reply(self._feature_disabled_message(), mention_author=False)
        return False

    def _feature_enabled(self) -> bool:
        if getattr(shared_config.features, "shard_tracker_enabled", False):
            return True
        toggles: Dict[str, bool] = {}
        for key in _FEATURE_TOGGLE_KEYS:
            try:
                toggles[key] = feature_flags.is_enabled(key)
            except Exception:
                log.exception("feature toggle check failed", extra={"feature": key})
        if toggles:
            try:
                shared_config.update_feature_flags_snapshot(toggles)
            except Exception:
                log.exception("failed to refresh feature toggle snapshot")
        return any(toggles.get(key, False) for key in _FEATURE_TOGGLE_KEYS)

    async def _handle_shards(
        self,
        ctx: commands.Context,
        shard_type: str | None,
    ) -> None:
        allowed, parent_channel, thread = await self._resolve_thread(ctx)
        if not allowed:
            return
        async with self._user_lock(ctx.author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(ctx.author.id, ctx.author.display_name or ctx.author.name)
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await self._handle_config_failure(ctx, exc)
                return
            record.snapshot_name(ctx.author.display_name or ctx.author.name)
            await self.store.save_record(config, record)
        if shard_type:
            kind = self._resolve_kind(shard_type)
            if kind is None:
                await ctx.reply(self._invalid_type_message(), mention_author=False)
                return
            display = self._build_display(record, kind)
            embed = build_detail_embed(member=ctx.author, display=display)
            view = None
        else:
            embed, view = self._build_summary_payload(ctx.author, record, thread)
        await self._send_thread_message(ctx, parent_channel, thread, embed, view)

    async def _handle_stash_set(
        self, ctx: commands.Context, shard_type: str, count: int
    ) -> None:
        kind = self._resolve_kind(shard_type)
        if kind is None:
            await ctx.reply(self._invalid_type_message(), mention_author=False)
            return
        count = max(0, count)
        async with self._user_lock(ctx.author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(ctx.author.id, ctx.author.display_name or ctx.author.name)
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await self._handle_config_failure(ctx, exc)
                return
            setattr(record, kind.stash_field, count)
            record.snapshot_name(ctx.author.display_name or ctx.author.name)
            await self.store.save_record(config, record)
        await ctx.reply(
            f"{kind.label} stash updated to **{count:,}**.",
            mention_author=False,
        )
        await self._log_action("stash_set", ctx.author, ctx.channel, f"{kind.label}={count}")

    async def _handle_mercy_set(
        self, ctx: commands.Context, shard_type: str, count: int
    ) -> None:
        key = self._resolve_kind_key(shard_type)
        if key == "mythic":
            attr = "primals_since_mythic"
            label = "Primal mythic"
        else:
            kind = self._resolve_kind(shard_type)
            if kind is None:
                await ctx.reply(self._invalid_type_message(), mention_author=False)
                return
            attr = kind.mercy_field
            label = kind.label
        count = max(0, count)
        async with self._user_lock(ctx.author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(ctx.author.id, ctx.author.display_name or ctx.author.name)
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await self._handle_config_failure(ctx, exc)
                return
            setattr(record, attr, count)
            record.snapshot_name(ctx.author.display_name or ctx.author.name)
            await self.store.save_record(config, record)
        await ctx.reply(
            f"{label} mercy counter set to **{count:,}**.",
            mention_author=False,
        )
        await self._log_action("mercy_set", ctx.author, ctx.channel, f"{label}={count}")

    async def _handle_lego(
        self, ctx: commands.Context, shard_type: str, after_count: int
    ) -> None:
        kind = self._resolve_kind(shard_type)
        if kind is None:
            await ctx.reply(self._invalid_type_message(), mention_author=False)
            return
        after = max(0, after_count)
        async with self._user_lock(ctx.author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(ctx.author.id, ctx.author.display_name or ctx.author.name)
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await self._handle_config_failure(ctx, exc)
                return
            setattr(record, kind.mercy_field, after)
            setattr(record, kind.timestamp_field, self._now_iso())
            record.snapshot_name(ctx.author.display_name or ctx.author.name)
            await self.store.save_record(config, record)
        await ctx.reply(
            f"Logged a {kind.label} LEGO. Counter now **{after:,}**.",
            mention_author=False,
        )
        await self._log_action("lego", ctx.author, ctx.channel, f"{kind.label} after={after}")

    async def _handle_mythic(self, ctx: commands.Context, after_count: int) -> None:
        after = max(0, after_count)
        async with self._user_lock(ctx.author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(ctx.author.id, ctx.author.display_name or ctx.author.name)
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await self._handle_config_failure(ctx, exc)
                return
            record.primals_since_mythic = after
            record.primals_since_lego = after
            record.last_primal_mythic_iso = self._now_iso()
            record.snapshot_name(ctx.author.display_name or ctx.author.name)
            await self.store.save_record(config, record)
        await ctx.reply(
            f"Logged a Primal mythic. Mercy counter now **{after:,}**.",
            mention_author=False,
        )
        await self._log_action("mythic", ctx.author, ctx.channel, f"Primal after={after}")

    def _apply_button_action(self, record: ShardRecord, kind: ShardKind, action: str) -> None:
        if action == "add":
            current = max(0, getattr(record, kind.stash_field, 0)) + 1
            setattr(record, kind.stash_field, current)
            return
        if action == "pull":
            owned = max(0, getattr(record, kind.stash_field, 0) - 1)
            setattr(record, kind.stash_field, owned)
            current_mercy = max(0, getattr(record, kind.mercy_field, 0)) + 1
            setattr(record, kind.mercy_field, current_mercy)
            if kind.key == "primal":
                record.primals_since_mythic = max(0, record.primals_since_mythic) + 1
            return

    async def _resolve_thread(
        self, ctx: commands.Context
    ) -> tuple[bool, discord.TextChannel | None, discord.Thread | None]:
        try:
            config = await self.store.get_config()
        except ShardTrackerConfigError as exc:
            await self._handle_config_failure(ctx, exc)
            return False, None, None
        channel = ctx.channel
        target_channel: discord.TextChannel | None = None
        thread: discord.Thread | None = None
        if isinstance(channel, discord.Thread):
            parent = channel.parent
            if not parent or parent.id != config.channel_id:
                await ctx.reply(self._channel_error_message(config.channel_id), mention_author=False)
                return False, None, None
            owner_id = self.threads.owner_id_for(channel)
            if owner_id and owner_id != ctx.author.id:
                await ctx.reply("Please use your own shard thread in the feature channel.", mention_author=False)
                return False, None, None
            target_channel = parent
            thread = channel
        elif isinstance(channel, discord.TextChannel):
            if channel.id != config.channel_id:
                await ctx.reply(self._channel_error_message(config.channel_id), mention_author=False)
                return False, None, None
            thread, _created = await self.threads.ensure_thread(parent=channel, user=ctx.author)
            target_channel = channel
        else:
            await ctx.reply(self._channel_error_message(config.channel_id), mention_author=False)
            return False, None, None
        return True, target_channel, thread

    async def _send_thread_message(
        self,
        ctx: commands.Context,
        parent: discord.TextChannel | None,
        thread: discord.Thread | None,
        embed: discord.Embed,
        view: discord.ui.View | None,
    ) -> None:
        if thread is None:
            await ctx.reply("Unable to locate or create your shard thread.", mention_author=False)
            return
        await thread.send(embed=embed, view=view)
        if parent and parent == ctx.channel:
            await ctx.reply(
                f"📬 Posted in your shard thread: {thread.mention}",
                mention_author=False,
            )

    def _build_summary_payload(
        self,
        member: discord.abc.User,
        record: ShardRecord,
        channel: discord.abc.GuildChannel | discord.Thread | None,
    ) -> tuple[discord.Embed, ShardTrackerView]:
        displays = [self._build_display(record, kind) for kind in SHARD_KINDS.values()]
        mythic_state = calculate_mercy(
            MERCY_PROFILES["primal_mythic"], max(0, record.primals_since_mythic)
        )
        embed = build_summary_embed(
            member=member,
            displays=displays,
            mythic_state=mythic_state,
            channel=channel or member.guild,  # type: ignore[arg-type]
        )
        labels = {kind.key: kind.label for kind in SHARD_KINDS.values()}
        view = ShardTrackerView(owner_id=getattr(member, "id", 0), controller=self, shard_labels=labels)
        return embed, view

    def _build_display(self, record: ShardRecord, kind: ShardKind) -> ShardDisplay:
        owned = max(0, getattr(record, kind.stash_field, 0))
        since = max(0, getattr(record, kind.mercy_field, 0))
        mercy = calculate_mercy(kind.mercy_profile, since)
        timestamp = getattr(record, kind.timestamp_field, "")
        return ShardDisplay(
            key=kind.key,
            label=kind.label,
            owned=owned,
            since=since,
            mercy=mercy,
            last_timestamp=timestamp,
        )

    def _resolve_kind(self, value: str | None) -> ShardKind | None:
        key = self._resolve_kind_key(value)
        if key in SHARD_KINDS:
            return SHARD_KINDS[key]
        return None

    def _resolve_kind_key(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = value.strip().lower()
        return _TYPE_ALIASES.get(normalized, normalized)

    def _invalid_type_message(self) -> str:
        options = ", ".join(sorted(kind.label.lower() for kind in SHARD_KINDS.values()))
        return f"Unknown shard type. Choose from: {options}, mythic."

    def _channel_error_message(self, channel_id: int) -> str:
        return f"Shard & Mercy tracking is only available in <#{channel_id}>."

    async def _handle_config_failure(
        self, ctx: commands.Context, exc: Exception
    ) -> None:
        await ctx.reply(
            "Shard tracker is misconfigured. Please contact an admin.",
            mention_author=False,
        )
        await self._notify_admins(str(exc))

    def _config_error_message(self, reason: str) -> str:
        return f"Shard tracker misconfigured: {reason}. Please contact an admin."

    async def _notify_admins(self, detail: str) -> None:
        mention = self._admin_mention()
        await runtime.send_log_message(f"❌ {mention} Shard tracker error: {detail}")

    def _admin_mention(self) -> str:
        roles = sorted(get_admin_role_ids())
        if roles:
            return f"<@&{roles[0]}>"
        return "@Administrator"

    async def _log_action(
        self,
        action: str,
        user: discord.abc.User,
        channel: discord.abc.Messageable,
        detail: str,
    ) -> None:
        guild = getattr(channel, "guild", None)
        log.info(
            "shard action",
            extra={
                "action": action,
                "user": getattr(user, "id", None),
                "detail": detail,
                "channel": getattr(channel, "id", None),
            },
        )
        await runtime.send_log_message(
            f"📘 Shards — {user_label(guild, getattr(user, 'id', None))} • {detail}"
        )

    def _user_lock(self, user_id: int) -> asyncio.Lock:
        lock = self._locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[user_id] = lock
        return lock

    def _now_iso(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShardTrackerCog(bot))
    log.info("Shard tracker cog loaded")

