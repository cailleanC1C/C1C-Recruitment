"""Recruiter command registration cog.

All recruiter-facing commands register here so modules remain side-effect free.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Dict, Optional, Tuple

import discord
from discord import InteractionResponded
from discord.ext import commands

from modules.common import config_access as config
from modules.common import feature_flags
from modules.coreops.helpers import tier
from modules.recruitment.views.recruiter_panel import RecruiterPanelView
from c1c_coreops.rbac import is_admin_member, is_recruiter

log = logging.getLogger(__name__)


class RecruiterPanelCog(commands.Cog):
    """Cog hosting the recruiter-facing `!clanmatch` command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._panel_owners: Dict[int, int] = {}
        self._owner_panels: Dict[int, Tuple[int, int]] = {}
        self._results_messages: Dict[int, Tuple[int, int]] = {}

    def register_panel(self, *, message_id: int, owner_id: int, channel_id: int) -> None:
        self._panel_owners[message_id] = owner_id
        self._owner_panels[owner_id] = (channel_id, message_id)

    def unregister_panel(self, message_id: int) -> None:
        owner_id = self._panel_owners.pop(message_id, None)
        if owner_id is not None:
            existing = self._owner_panels.get(owner_id)
            if existing and existing[1] == message_id:
                self._owner_panels.pop(owner_id, None)

    def register_results_message(
        self, owner_id: int, *, channel_id: int, message_id: int
    ) -> None:
        self._results_messages[owner_id] = (channel_id, message_id)

    def unregister_results_message(self, owner_id: int) -> None:
        self._results_messages.pop(owner_id, None)

    def _results_for_owner(self, owner_id: int) -> Optional[Tuple[int, int]]:
        return self._results_messages.get(owner_id)

    def _owner_for(self, message_id: int) -> Optional[int]:
        return self._panel_owners.get(message_id)

    def _panel_for_owner(self, owner_id: int) -> Optional[Tuple[int, int]]:
        return self._owner_panels.get(owner_id)

    async def _hydrate_results_message(
        self, owner_id: int, view: "RecruiterPanelView"
    ) -> None:
        info = self._results_for_owner(owner_id)
        if not info:
            return

        channel_id, message_id = info

        channel = self.bot.get_channel(channel_id) if self.bot else None
        if channel is None and self.bot:
            with contextlib.suppress(Exception):
                channel = await self.bot.fetch_channel(channel_id)

        if not isinstance(channel, discord.abc.Messageable):
            self.unregister_results_message(owner_id)
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            self.unregister_results_message(owner_id)
            return
        except discord.HTTPException:
            log.exception(
                "[clanmatch] failed to fetch results message: channel_id=%s message_id=%s",
                channel_id,
                message_id,
            )
            return

        view.results_message = message
        view.results_view = None
        try:
            view._last_results_embeds = [
                embed.copy() for embed in (message.embeds or [])
            ]
        except Exception:
            view._last_results_embeds = []
        view._last_results_content = message.content
        with contextlib.suppress(Exception):
            await message.edit(view=None)

    async def _resolve_recruiter_panel_channel(
        self, ctx: commands.Context
    ) -> tuple[discord.abc.MessageableChannel | None, bool]:
        """Locate the configured recruiter thread if available."""

        mode = str(config.get_panel_thread_mode("channel")).strip().lower()
        if mode != "fixed":
            return ctx.channel, False

        thread_id = config.get_panel_fixed_thread_id()
        if not thread_id:
            return ctx.channel, False

        channel: discord.abc.MessageableChannel | None = None

        if ctx.guild:
            thread = ctx.guild.get_thread(thread_id)
            if isinstance(thread, discord.Thread):
                channel = thread
            if channel is None:
                try:
                    fetched = await ctx.guild.fetch_channel(thread_id)
                except discord.NotFound:
                    log.error("[clanmatch] thread not found: %s", thread_id)
                    return None, False
                except discord.Forbidden:
                    log.exception(
                        "[clanmatch] thread fetch forbidden: guild=%s thread_id=%s",
                        ctx.guild.id,
                        thread_id,
                    )
                    return None, False
                except discord.HTTPException:
                    log.exception(
                        "[clanmatch] thread fetch HTTP failure: guild=%s thread_id=%s",
                        ctx.guild.id,
                        thread_id,
                    )
                    return None, False
                else:
                    if isinstance(fetched, discord.abc.Messageable):
                        channel = fetched  # type: ignore[assignment]

        if channel is None and self.bot:
            cached = self.bot.get_channel(thread_id)
            if isinstance(cached, discord.abc.Messageable):
                channel = cached  # type: ignore[assignment]

        if channel is None and self.bot:
            try:
                fetched = await self.bot.fetch_channel(thread_id)
            except discord.NotFound:
                log.error("[clanmatch] thread not found (bot-level): %s", thread_id)
                return None, False
            except discord.Forbidden:
                log.exception(
                    "[clanmatch] bot fetch forbidden for thread_id=%s", thread_id
                )
                return None, False
            except discord.HTTPException:
                log.exception(
                    "[clanmatch] bot fetch HTTP failure for thread_id=%s", thread_id
                )
                return None, False
            else:
                if isinstance(fetched, discord.abc.Messageable):
                    channel = fetched  # type: ignore[assignment]

        if channel is None:
            return None, False

        guild = getattr(channel, "guild", None)
        if guild and ctx.guild and guild.id != ctx.guild.id:
            log.error(
                "[clanmatch] thread resolve guild mismatch: expected=%s actual=%s thread_id=%s",
                ctx.guild.id,
                guild.id,
                thread_id,
            )
            return None, False

        if isinstance(channel, discord.Thread) and channel.archived:
            try:
                await channel.edit(archived=False)
            except discord.Forbidden:
                log.exception(
                    "[clanmatch] failed to unarchive thread_id=%s", thread_id
                )
            except discord.HTTPException:
                log.exception(
                    "[clanmatch] HTTP failure unarchiving thread_id=%s", thread_id
                )

        log.info(
            "[clanmatch] target resolve ok: guild=%s thread_id=%s type=%s",
            getattr(guild, "id", None),
            thread_id,
            type(channel).__name__,
        )

        return channel, True

    @tier("staff")
    @commands.command(
        name="clanmatch",
        help="Launches the text-only recruiter panel used to match recruits with clans.",
    )
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def clanmatch(self, ctx: commands.Context) -> None:
        """Open the recruiter panel to find clans for a recruit."""

        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("⚠️ `!clanmatch` can only be used in a server.")
            return

        if not (is_recruiter(ctx) or is_admin_member(ctx)):
            await ctx.reply(
                "⚠️ Only **Recruitment Scouts/Coordinators** (or Admins) can use `!clanmatch`.",
                mention_author=False,
            )
            return

        view = RecruiterPanelView(self, ctx.author.id)
        panel_embeds, results_embeds = await view._build_page()
        view._last_panel_embeds = [embed.copy() for embed in panel_embeds]
        view._last_results_embeds = [embed.copy() for embed in results_embeds]
        view._last_results_content = None

        existing_panel = self._panel_for_owner(ctx.author.id)
        if existing_panel:
            channel_id, message_id = existing_panel
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                try:
                    message = await channel.fetch_message(message_id)
                except Exception:
                    self.unregister_panel(message_id)
                else:
                    view.message = message
                    await message.edit(embeds=panel_embeds, view=view)
                    self.register_panel(
                        message_id=message.id,
                        owner_id=ctx.author.id,
                        channel_id=channel.id,
                    )
                    await self._hydrate_results_message(ctx.author.id, view)
                    if channel != ctx.channel:
                        try:
                            await ctx.reply(
                                f"{ctx.author.mention} your recruiter panel is in {channel.mention}.",
                                mention_author=False,
                                allowed_mentions=discord.AllowedMentions(users=[ctx.author]),
                                suppress_embeds=True,
                            )
                        except Exception:
                            pass
                    return

        target, redirected = await self._resolve_recruiter_panel_channel(ctx)
        if target is None:
            await ctx.reply(
                "⚠️ I couldn't open the recruiter panel. Please contact an admin.",
                mention_author=False,
            )
            return

        log.info(
            "[clanmatch] sending panel: channel_id=%s redirected=%s",
            getattr(target, "id", None),
            redirected,
        )

        try:
            sent = await target.send(embeds=panel_embeds, view=view)
        except discord.Forbidden:
            log.exception(
                "[clanmatch] send forbidden: thread_id=%s",
                getattr(target, "id", None),
            )
            await ctx.reply(
                "⚠️ I couldn't open the recruiter panel due to missing permissions.",
                mention_author=False,
            )
            return
        except discord.HTTPException:
            log.exception(
                "[clanmatch] send HTTP failure: thread_id=%s",
                getattr(target, "id", None),
            )
            await ctx.reply(
                "⚠️ I couldn't open the recruiter panel. Please try again later.",
                mention_author=False,
            )
            return

        view.message = sent
        self.register_panel(
            message_id=sent.id,
            owner_id=ctx.author.id,
            channel_id=sent.channel.id,
        )

        await self._hydrate_results_message(ctx.author.id, view)

        if redirected and target is not ctx.channel:
            try:
                await ctx.reply(
                    f"{ctx.author.mention} I opened your recruiter panel in {target.mention}.",
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions(users=[ctx.author]),
                    suppress_embeds=True,
                )
            except Exception:  # pragma: no cover - pointer best effort
                pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        message = getattr(interaction, "message", None)
        if not message:
            return
        owner_id = self._owner_for(message.id)
        if owner_id is None:
            return
        if interaction.user and interaction.user.id != owner_id:
            try:
                await interaction.response.send_message(
                    "⚠️ Not your panel. Type **!clanmatch** to summon your own.",
                    ephemeral=True,
                )
            except InteractionResponded:
                try:
                    await interaction.followup.send(
                        "⚠️ Not your panel. Type **!clanmatch** to summon your own.",
                        ephemeral=True,
                    )
                except Exception:
                    pass


async def setup(bot: commands.Bot) -> None:
    if not feature_flags.is_enabled("recruiter_panel"):
        return
    await bot.add_cog(RecruiterPanelCog(bot))
