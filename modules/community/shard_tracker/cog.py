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
from .mercy import MERCY_CONFIGS, MercyConfig, MercySnapshot, mercy_state
from .threads import ShardThreadRouter
from .views import (
    MythicDisplay,
    ShardDisplay,
    ShardTrackerController,
    ShardTrackerView,
    build_detail_embed,
    build_last_pulls_embed,
    build_overview_embed,
)
from modules.common import runtime

log = logging.getLogger("c1c.shards.cog")


@dataclass(frozen=True)
class ShardKind:
    key: str
    label: str
    stash_field: str
    mercy_field: str
    mercy_config: MercyConfig
    timestamp_field: str
    depth_field: str


SHARD_KINDS: Dict[str, ShardKind] = {
    "ancient": ShardKind(
        key="ancient",
        label="Ancient",
        stash_field="ancients_owned",
        mercy_field="ancients_since_lego",
        mercy_config=MERCY_CONFIGS["ancient"],
        timestamp_field="last_ancient_lego_iso",
        depth_field="last_ancient_lego_depth",
    ),
    "void": ShardKind(
        key="void",
        label="Void",
        stash_field="voids_owned",
        mercy_field="voids_since_lego",
        mercy_config=MERCY_CONFIGS["void"],
        timestamp_field="last_void_lego_iso",
        depth_field="last_void_lego_depth",
    ),
    "sacred": ShardKind(
        key="sacred",
        label="Sacred",
        stash_field="sacreds_owned",
        mercy_field="sacreds_since_lego",
        mercy_config=MERCY_CONFIGS["sacred"],
        timestamp_field="last_sacred_lego_iso",
        depth_field="last_sacred_lego_depth",
    ),
    "primal": ShardKind(
        key="primal",
        label="Primal",
        stash_field="primals_owned",
        mercy_field="primals_since_lego",
        mercy_config=MERCY_CONFIGS["primal"],
        timestamp_field="last_primal_lego_iso",
        depth_field="last_primal_lego_depth",
    ),
}

_BASE_RATES = {
    "Ancient Legendary": "0.5%",
    "Void Legendary": "0.5%",
    "Sacred Legendary": "6%",
    "Primal Legendary": "1%",
    "Primal Mythical": "0.5%",
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


class ShardTracker(commands.Cog, ShardTrackerController):
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
        usage="!shards [type]",
    )
    @commands.group(
        name="shards",
        invoke_without_command=True,
        help=(
            "Shard & Mercy tracker with overview and detail tabs. Only runs in the Shards & Mercy "
            "channel; creates your personal thread when needed."
        ),
    )
    async def shards(self, ctx: commands.Context, *, shard_type: str | None = None) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_shards(ctx, shard_type)

    @tier("user")
    @help_metadata(
        function_group="milestones",
        section="community",
        access_tier="user",
        usage="!shards set <type> <count>",
    )
    @shards.command(
        name="set",
        help="Set the shard stash count for a specific type (non-negative integers only).",
    )
    async def shards_set(self, ctx: commands.Context, shard_type: str, count: int) -> None:
        if not await self._ensure_feature_enabled(ctx):
            return
        await self._handle_stash_set(ctx, shard_type, count)

    # === Button controller ===

    async def handle_button_interaction(
        self,
        *,
        interaction: discord.Interaction,
        custom_id: str,
        active_tab: str,
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

        action = self._parse_custom_id(custom_id)
        if action is None:
            await interaction.response.send_message(
                "Unknown action for shard tracker.", ephemeral=True
            )
            return

        async with self._user_lock(ctx_author.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(
                    ctx_author.id, ctx_author.display_name or ctx_author.name
                )
            except ShardTrackerConfigError as exc:
                await interaction.response.send_message(
                    self._config_error_message(str(exc)),
                    ephemeral=True,
                )
                await self._notify_admins(str(exc))
                return
            except ShardTrackerSheetError as exc:
                await interaction.response.send_message(
                    "Shard tracker sheet misconfigured. Please contact an admin.",
                    ephemeral=True,
                )
                await self._notify_admins(str(exc))
                return

            if action[0] == "tab":
                new_tab = action[1]
                embed, view = self._build_panel(
                    ctx_author, record, interaction.channel, new_tab
                )
                await interaction.response.edit_message(embed=embed, view=view)
                return

            if action[0] == "log":
                _, shard_key = action
                modal = _LegendaryLogModal(
                    shard_key=shard_key,
                    controller=self,
                    owner_id=ctx_author.id,
                    active_tab=active_tab,
                )
                await interaction.response.send_modal(modal)
                return

            if action[0] == "log_mythic":
                modal = _MythicLogModal(
                    controller=self,
                    owner_id=ctx_author.id,
                    active_tab=active_tab,
                )
                await interaction.response.send_modal(modal)
                return

            # adjustments
            action_type, shard_key, delta = action
            if action_type == "mythic_adjust":
                self._adjust_mythic_counter(record, delta)
            else:
                kind = self._resolve_kind(shard_key)
                if kind is None:
                    await interaction.response.send_message(
                        "Unknown shard type for this button.", ephemeral=True
                    )
                    return
                self._apply_delta(record, kind, delta)
            record.snapshot_name(ctx_author.display_name or ctx_author.name)
            await self.store.save_record(config, record)
            embed, view = self._build_panel(ctx_author, record, interaction.channel, active_tab)
            await interaction.response.edit_message(embed=embed, view=view)
            await self._log_action(
                "button",
                ctx_author,
                interaction.channel,
                f"{custom_id}",
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
        tab = self._resolve_kind_key(shard_type) if shard_type else "overview"
        if tab and tab not in SHARD_KINDS:
            tab = "overview"
        embed, view = self._build_panel(ctx.author, record, thread, tab)
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

    def _parse_custom_id(
        self, custom_id: str
    ) -> tuple[str, str | None, int] | tuple[str, str] | None:
        if custom_id.startswith("tab:"):
            return ("tab", custom_id.split(":", 1)[1])
        if custom_id.endswith("got_legendary"):
            shard_key = custom_id.split(":", 1)[0]
            return ("log", shard_key)
        if custom_id.endswith("got_mythical"):
            return ("log_mythic", None)
        parts = custom_id.split(":")
        if len(parts) == 3 and parts[1] == "add":
            shard_key, _, delta_raw = parts
            try:
                delta = int(delta_raw)
            except ValueError:
                return None
            if shard_key == "primal_mythic":
                return ("mythic_adjust", shard_key, delta)
            return ("adjust", shard_key, delta)
        return None

    def _apply_delta(self, record: ShardRecord, kind: ShardKind, delta: int) -> None:
        owned = max(0, getattr(record, kind.stash_field, 0))
        new_owned = max(0, owned + delta)
        setattr(record, kind.stash_field, new_owned)
        actual_delta = new_owned - owned
        if actual_delta < 0:
            pulled = abs(actual_delta)
            current_mercy = max(0, getattr(record, kind.mercy_field, 0))
            setattr(record, kind.mercy_field, current_mercy + pulled)
            if kind.key == "primal":
                record.primals_since_mythic = max(0, record.primals_since_mythic) + pulled

    def _adjust_mythic_counter(self, record: ShardRecord, delta: int) -> None:
        record.primals_since_mythic = max(0, record.primals_since_mythic + delta)

    async def process_legendary_modal(
        self,
        *,
        interaction: discord.Interaction,
        shard_key: str,
        total_pulled: int,
        legend_index: int,
        active_tab: str,
    ) -> None:
        kind = self._resolve_kind(shard_key)
        if kind is None:
            await interaction.response.send_message("Unknown shard type.", ephemeral=True)
            return
        if legend_index > total_pulled:
            await interaction.response.send_message(
                "Legendary shard index cannot exceed total pulled.", ephemeral=True
            )
            return
        async with self._user_lock(interaction.user.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(
                    interaction.user.id,
                    interaction.user.display_name or interaction.user.name,
                )
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await interaction.response.send_message(
                    self._config_error_message(str(exc)), ephemeral=True
                )
                await self._notify_admins(str(exc))
                return
            self._apply_logged_legendary(record, kind, total_pulled, legend_index)
            record.snapshot_name(interaction.user.display_name or interaction.user.name)
            await self.store.save_record(config, record)
        embed, view = self._build_panel(interaction.user, record, interaction.channel, active_tab)
        await interaction.response.edit_message(embed=embed, view=view)
        await self._log_action(
            "legendary_modal",
            interaction.user,
            interaction.channel,
            f"{kind.label} total={total_pulled} index={legend_index}",
        )

    async def process_mythic_modal(
        self,
        *,
        interaction: discord.Interaction,
        total_pulled: int,
        mythic_index: int,
        active_tab: str,
    ) -> None:
        if mythic_index > total_pulled:
            await interaction.response.send_message(
                "Mythical shard index cannot exceed total pulled.", ephemeral=True
            )
            return
        kind = SHARD_KINDS["primal"]
        async with self._user_lock(interaction.user.id):
            try:
                config = await self.store.get_config()
                record = await self.store.load_record(
                    interaction.user.id,
                    interaction.user.display_name or interaction.user.name,
                )
            except (ShardTrackerConfigError, ShardTrackerSheetError) as exc:
                await interaction.response.send_message(
                    self._config_error_message(str(exc)), ephemeral=True
                )
                await self._notify_admins(str(exc))
                return
            self._apply_logged_mythic(record, kind, total_pulled, mythic_index)
            record.snapshot_name(interaction.user.display_name or interaction.user.name)
            await self.store.save_record(config, record)
        embed, view = self._build_panel(interaction.user, record, interaction.channel, active_tab)
        await interaction.response.edit_message(embed=embed, view=view)
        await self._log_action(
            "mythic_modal",
            interaction.user,
            interaction.channel,
            f"Primal total={total_pulled} index={mythic_index}",
        )

    def _apply_logged_legendary(
        self, record: ShardRecord, kind: ShardKind, total_pulled: int, legend_index: int
    ) -> None:
        total = max(1, total_pulled)
        index = max(1, legend_index)
        pre = index
        post = max(0, total - index)
        previous = max(0, getattr(record, kind.mercy_field, 0))
        depth = previous + pre
        setattr(record, kind.mercy_field, post)
        setattr(record, kind.depth_field, depth)
        setattr(record, kind.timestamp_field, self._now_iso())
        if kind.key == "primal":
            record.primals_since_mythic = max(0, record.primals_since_mythic) + total
        owned = max(0, getattr(record, kind.stash_field, 0))
        setattr(record, kind.stash_field, max(0, owned - total))

    def _apply_logged_mythic(
        self, record: ShardRecord, kind: ShardKind, total_pulled: int, mythic_index: int
    ) -> None:
        total = max(1, total_pulled)
        index = max(1, mythic_index)
        pre = index
        post = max(0, total - index)
        previous = max(0, record.primals_since_mythic)
        depth = previous + pre
        record.primals_since_mythic = post
        setattr(record, kind.mercy_field, post)
        timestamp = self._now_iso()
        record.last_primal_mythic_iso = timestamp
        record.last_primal_mythic_depth = depth
        setattr(record, kind.timestamp_field, timestamp)
        setattr(record, kind.depth_field, depth)
        owned = max(0, getattr(record, kind.stash_field, 0))
        setattr(record, kind.stash_field, max(0, owned - total))

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

    def _build_panel(
        self,
        member: discord.abc.User,
        record: ShardRecord,
        channel: discord.abc.GuildChannel | discord.Thread | None,
        active_tab: str,
    ) -> tuple[discord.Embed, ShardTrackerView]:
        displays = [self._build_display(record, kind) for kind in SHARD_KINDS.values()]
        mythic = self._build_mythic_display(record)
        tab = active_tab if active_tab else "overview"

        if tab == "last_pulls":
            embed = build_last_pulls_embed(
                member=member,
                displays=displays,
                mythic=mythic,
                base_rates=_BASE_RATES,
            )
        elif tab in SHARD_KINDS:
            target = next((d for d in displays if d.key == tab), displays[0])
            embed = build_detail_embed(
                member=member,
                display=target,
                mythic=mythic if tab == "primal" else None,
            )
        else:
            embed = build_overview_embed(member=member, displays=displays, mythic=mythic)

        labels = {kind.key: kind.label for kind in SHARD_KINDS.values()}
        view = ShardTrackerView(
            owner_id=getattr(member, "id", 0),
            controller=self,
            shard_labels=labels,
            active_tab=tab,
        )
        return embed, view

    def _build_display(self, record: ShardRecord, kind: ShardKind) -> ShardDisplay:
        owned = max(0, getattr(record, kind.stash_field, 0))
        since = max(0, getattr(record, kind.mercy_field, 0))
        mercy = mercy_state(kind.key, since)
        timestamp = getattr(record, kind.timestamp_field, "")
        depth = max(0, getattr(record, kind.depth_field, 0))
        return ShardDisplay(
            key=kind.key,
            label=kind.label,
            owned=owned,
            mercy=mercy,
            last_timestamp=timestamp,
            last_depth=depth,
        )

    def _build_mythic_display(self, record: ShardRecord) -> MythicDisplay:
        state = mercy_state("primal_mythic", max(0, record.primals_since_mythic))
        return MythicDisplay(
            mercy=state,
            last_timestamp=record.last_primal_mythic_iso,
            last_depth=max(0, record.last_primal_mythic_depth),
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
        return f"Unknown shard type. Choose from: {options}."

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


class _LegendaryLogModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        shard_key: str,
        controller: ShardTracker,
        owner_id: int,
        active_tab: str,
    ) -> None:
        label = SHARD_KINDS.get(shard_key).label if SHARD_KINDS.get(shard_key) else shard_key.title()
        super().__init__(title=f"Log Legendary pull — {label} Shards")
        self.shard_key = shard_key
        self.controller = controller
        self.owner_id = owner_id
        self.active_tab = active_tab
        self.total_pulled = discord.ui.TextInput(
            label="Total shards pulled in this session",
            min_length=1,
            max_length=6,
            required=True,
            placeholder="e.g., 10",
        )
        self.legend_index = discord.ui.TextInput(
            label="On which shard did the Legendary appear?",
            min_length=1,
            max_length=6,
            required=True,
            placeholder="e.g., 3",
        )
        self.add_item(self.total_pulled)
        self.add_item(self.legend_index)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the tracker owner can log pulls.", ephemeral=True)
            return
        try:
            total = int(str(self.total_pulled.value))
            index = int(str(self.legend_index.value))
        except (TypeError, ValueError):
            await interaction.response.send_message("Please provide numeric values.", ephemeral=True)
            return
        if total < 1 or index < 1:
            await interaction.response.send_message("Values must be at least 1.", ephemeral=True)
            return
        await self.controller.process_legendary_modal(
            interaction=interaction,
            shard_key=self.shard_key,
            total_pulled=total,
            legend_index=index,
            active_tab=self.active_tab,
        )


class _MythicLogModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        controller: ShardTracker,
        owner_id: int,
        active_tab: str,
    ) -> None:
        super().__init__(title="Log Mythical pull — Primal Shards")
        self.controller = controller
        self.owner_id = owner_id
        self.active_tab = active_tab
        self.total_pulled = discord.ui.TextInput(
            label="Total primal shards pulled in this session",
            min_length=1,
            max_length=6,
            required=True,
            placeholder="e.g., 10",
        )
        self.mythic_index = discord.ui.TextInput(
            label="On which shard did the Mythical appear?",
            min_length=1,
            max_length=6,
            required=True,
            placeholder="e.g., 7",
        )
        self.add_item(self.total_pulled)
        self.add_item(self.mythic_index)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the tracker owner can log pulls.", ephemeral=True)
            return
        try:
            total = int(str(self.total_pulled.value))
            index = int(str(self.mythic_index.value))
        except (TypeError, ValueError):
            await interaction.response.send_message("Please provide numeric values.", ephemeral=True)
            return
        if total < 1 or index < 1:
            await interaction.response.send_message("Values must be at least 1.", ephemeral=True)
            return
        await self.controller.process_mythic_modal(
            interaction=interaction,
            total_pulled=total,
            mythic_index=index,
            active_tab=self.active_tab,
        )


