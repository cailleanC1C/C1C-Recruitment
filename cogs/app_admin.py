"""App-level administrative commands registered under the cogs namespace."""

from __future__ import annotations

import discord
from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import admin_only
from modules.common import feature_flags, runtime as runtime_helpers
from modules.common.logs import channel_label
from modules.ops import cluster_role_map, server_map
from shared.config import get_role_map_channel_id
from shared.sheets import recruitment as recruitment_sheet


class AppAdmin(commands.Cog):
    """Lightweight administrative utilities for bot operators."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        command = self.bot.get_command("ping")
        if command is None:
            return

        extras = getattr(command, "extras", None)
        if not isinstance(extras, dict):
            extras = {}
            setattr(command, "extras", extras)

        extras.setdefault("function_group", "operational")
        extras.setdefault("access_tier", "admin")

        try:
            setattr(command, "function_group", "operational")
        except Exception:
            pass
        try:
            setattr(command, "access_tier", "admin")
        except Exception:
            pass

        coreops = self.bot.get_cog("CoreOpsCog")
        apply_attrs = getattr(coreops, "_apply_metadata_attributes", None)
        if callable(apply_attrs):
            apply_attrs(command)

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.command(
        name="ping",
        hidden=True,
        help="Quick admin check to confirm the bot is responsive.",
    )
    @admin_only()
    async def ping(self, ctx: commands.Context) -> None:
        """React with a paddle to confirm the bot processed the request."""

        try:
            await ctx.message.add_reaction("🏓")
        except Exception:
            # Reaction failures are non-fatal (missing perms, deleted message, etc.).
            pass

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.group(
        name="servermap",
        invoke_without_command=True,
        hidden=True,
        help="Admin tools for the automated #server-map post.",
    )
    @admin_only()
    async def servermap(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        await ctx.reply("Usage: !servermap refresh", mention_author=False)

    @servermap.command(
        name="refresh",
        help="Rebuild the #server-map channel immediately from the live guild structure.",
    )
    @admin_only()
    async def servermap_refresh(self, ctx: commands.Context) -> None:
        if not feature_flags.is_enabled("SERVER_MAP"):
            await ctx.reply(
                "Server map feature is currently disabled in FeatureToggles.",
                mention_author=False,
            )
            await runtime_helpers.send_log_message(
                "📘 Server map — skipped • reason=feature_disabled"
            )
            return

        result = await server_map.refresh_server_map(self.bot, force=True, actor="command")
        if result.status == "ok":
            await ctx.reply(
                f"Server map refreshed — messages={result.message_count} • chars={result.total_chars}.",
                mention_author=False,
            )
            return
        if result.status == "disabled":
            await ctx.reply(
                "Server map feature is currently disabled in FeatureToggles.",
                mention_author=False,
            )
            return
        reason = result.reason or "unknown"
        await ctx.reply(
            f"Server map refresh failed ({reason}). Check logs for details.",
            mention_author=False,
        )

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.command(
        name="whoweare",
        hidden=True,
        help="Generate the live Who We Are overview from the WhoWeAre sheet.",
    )
    @admin_only()
    async def whoweare(self, ctx: commands.Context) -> None:
        guild = getattr(ctx, "guild", None)
        guild_name = getattr(guild, "name", "unknown guild")

        if not feature_flags.is_enabled("ClusterRoleMap"):
            await ctx.reply(
                "Cluster role map feature is disabled in FeatureToggles.",
                mention_author=False,
            )
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} • status=disabled"
            )
            return

        if guild is None:
            await ctx.reply(
                "This command can only be used inside a Discord guild.",
                mention_author=False,
            )
            return

        tab_name = recruitment_sheet.get_role_map_tab_name()
        try:
            entries = await cluster_role_map.fetch_role_map_rows(tab_name=tab_name)
        except cluster_role_map.RoleMapLoadError as exc:
            await ctx.reply(
                f"I couldn’t read the role map sheet (`{tab_name}`). Please check Config and try again.",
                mention_author=False,
            )
            reason = str(exc) or "unknown"
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} • status=error • reason={reason}"
            )
            return

        render = cluster_role_map.build_role_map_render(guild, entries)

        channel_id = get_role_map_channel_id()
        target_channel, used_fallback = await runtime_helpers.resolve_configured_message_channel(
            ctx,
            bot=self.bot,
            channel_id=channel_id,
            expected_guild=guild,
        )
        if target_channel is None:
            await ctx.reply(
                "I couldn’t determine where to post the role map. Please try again in a guild channel.",
                mention_author=False,
            )
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} • status=error • reason=no_channel"
            )
            return

        if used_fallback:
            requested = channel_id or "ctx"
            fallback_label = channel_label(guild, getattr(target_channel, "id", None))
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} "
                f"• channel_fallback={fallback_label} • requested_channel={requested}"
            )

        cleaned = 0
        bot_user = getattr(self.bot, "user", None)
        bot_user_id = getattr(bot_user, "id", None)
        try:
            cleaned = await cluster_role_map.cleanup_previous_role_map_messages(
                target_channel,
                bot_id=bot_user_id,
            )
        except Exception:  # pragma: no cover - defensive logging
            log_reason = "cleanup_failed"
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} • status=warning • reason={log_reason}"
            )
        else:
            if cleaned:
                await runtime_helpers.send_log_message(
                    f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} • cleaned_messages={cleaned}"
                )

        try:
            index_message = await target_channel.send(cluster_role_map.build_index_placeholder())
        except discord.HTTPException as exc:
            reason = str(exc) or "index_send_failed"
            await ctx.reply(
                "I couldn’t post the role map. Please check channel permissions and try again.",
                mention_author=False,
            )
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} "
                f"• status=error • step=index_send • reason={reason}"
            )
            return

        jump_entries: list[cluster_role_map.IndexLink] = []
        for category in render.categories:
            body = cluster_role_map.build_category_message(category)
            if not body.strip():
                continue
            try:
                message = await target_channel.send(body)
            except discord.HTTPException as exc:
                reason = str(exc) or "category_send_failed"
                await runtime_helpers.send_log_message(
                    f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} "
                    f"• status=error • step=category_send • category={category.name} • reason={reason}"
                )
                continue
            jump_entries.append(
                cluster_role_map.IndexLink(
                    name=category.name,
                    emoji=category.emoji,
                    url=cluster_role_map.build_jump_url(
                        getattr(guild, "id", 0),
                        getattr(target_channel, "id", 0),
                        getattr(message, "id", 0),
                    ),
                )
            )

        if not jump_entries:
            if render.category_count:
                empty_reason = "_(Unable to post any categories — check channel permissions and try again.)_"
            else:
                empty_reason = "_(No categories are currently available — check the WhoWeAre sheet.)_"
        else:
            empty_reason = None

        try:
            final_index = cluster_role_map.build_index_message(jump_entries, empty_reason=empty_reason)
            await index_message.edit(content=final_index)
        except discord.HTTPException as exc:
            reason = str(exc) or "index_edit_failed"
            await runtime_helpers.send_log_message(
                f"📘 **Cluster role map** — cmd=whoweare • guild={guild_name} "
                f"• status=error • step=index_edit • reason={reason}"
            )

        if getattr(target_channel, "id", None) == getattr(ctx.channel, "id", None):
            ack_message = "Cluster role map updated."
        else:
            mention = getattr(target_channel, "mention", None)
            if not mention:
                label = channel_label(guild, getattr(target_channel, "id", None))
                mention = label or "the configured channel"
            ack_message = f"Cluster role map refreshed in {mention}."
        await ctx.reply(ack_message, mention_author=False)

        target_label = channel_label(guild, getattr(target_channel, "id", None))
        await runtime_helpers.send_log_message(
            "📘 **Cluster role map** — "
            f"cmd=whoweare • guild={guild_name} • categories={render.category_count} "
            f"• roles={render.role_count} • unassigned_roles={render.unassigned_roles} "
            f"• category_messages={len(jump_entries)} • target_channel={target_label}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AppAdmin(bot))
