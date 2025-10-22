"""Recruiter command registration cog.

All recruiter-facing commands register here so modules remain side-effect free.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import discord
from discord import InteractionResponded
from discord.ext import commands

from modules.common import feature_flags
from modules.coreops.helpers import tier
from modules.recruitment.views.recruiter_panel import RecruiterPanelView
from shared.config import get_recruiters_thread_id
from shared.coreops_rbac import is_admin_member, is_recruiter


class RecruiterPanelCog(commands.Cog):
    """Cog hosting the recruiter-facing `!clanmatch` command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._panel_owners: Dict[int, int] = {}
        self._owner_panels: Dict[int, Tuple[int, int]] = {}

    def register_panel(self, *, message_id: int, owner_id: int, channel_id: int) -> None:
        self._panel_owners[message_id] = owner_id
        self._owner_panels[owner_id] = (channel_id, message_id)

    def unregister_panel(self, message_id: int) -> None:
        owner_id = self._panel_owners.pop(message_id, None)
        if owner_id is not None:
            existing = self._owner_panels.get(owner_id)
            if existing and existing[1] == message_id:
                self._owner_panels.pop(owner_id, None)

    def _owner_for(self, message_id: int) -> Optional[int]:
        return self._panel_owners.get(message_id)

    def _panel_for_owner(self, owner_id: int) -> Optional[Tuple[int, int]]:
        return self._owner_panels.get(owner_id)

    async def _resolve_recruiter_panel_channel(
        self, ctx: commands.Context
    ) -> tuple[discord.abc.MessageableChannel, bool]:
        """Locate the configured recruiter thread if available."""

        thread_id = get_recruiters_thread_id()
        if not thread_id:
            return ctx.channel, False

        channel: discord.abc.GuildChannel | discord.Thread | None = None
        if self.bot:
            channel = self.bot.get_channel(thread_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(thread_id)
                except Exception:
                    channel = None

        if isinstance(channel, discord.Thread):
            if channel.guild and ctx.guild and channel.guild.id != ctx.guild.id:
                return ctx.channel, False
            if channel.archived:
                try:
                    await channel.edit(archived=False)
                except Exception:
                    pass
        elif isinstance(channel, discord.TextChannel):
            if channel.guild and ctx.guild and channel.guild.id != ctx.guild.id:
                return ctx.channel, False
        else:
            return ctx.channel, False

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
        embeds, _ = await view._build_page()
        view._last_embeds = [embed.copy() for embed in embeds]

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
                    await message.edit(embeds=embeds, view=view)
                    self.register_panel(
                        message_id=message.id,
                        owner_id=ctx.author.id,
                        channel_id=channel.id,
                    )
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
        sent = await target.send(embeds=embeds, view=view)
        view.message = sent
        self.register_panel(
            message_id=sent.id,
            owner_id=ctx.author.id,
            channel_id=sent.channel.id,
        )

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
