"""Controller for the onboarding wizard persistent panel."""

from __future__ import annotations

import discord
from discord.ext import commands


class WizardController:
    """Coordinate onboarding wizard interactions for a single user session."""

    def __init__(self, bot: commands.Bot, sessions, renderer) -> None:
        self.bot = bot
        self.sessions = sessions
        self.renderer = renderer
        self.log = getattr(bot, "logger", None)

    async def _send_or_edit_panel(self, interaction: discord.Interaction, session) -> None:
        """Single-message policy: always edit the same panel message."""

        content, view = self.renderer.render(session)
        edit_count = 0
        followup_count = 0

        if not getattr(session, "panel_message_id", None):
            base_msg = getattr(interaction, "message", None)
            if base_msg is not None:
                session.panel_message_id = base_msg.id
                await base_msg.edit(content=content, view=view)
                edit_count += 1
            else:
                msg = await interaction.channel.send(content=content, view=view)
                session.panel_message_id = msg.id
                edit_count += 1
        else:
            try:
                msg = await interaction.channel.fetch_message(session.panel_message_id)
                await msg.edit(content=content, view=view)
                edit_count += 1
            except discord.NotFound:
                msg = await interaction.channel.send(content=content, view=view)
                session.panel_message_id = msg.id
                edit_count += 1

        await self.sessions.save(session)

        if self.log is not None:
            try:
                self.log.info(
                    "wizard:render",
                    extra={
                        "panel_message_id": session.panel_message_id,
                        "edit_count": edit_count,
                        "followup_count": followup_count,
                    },
                )
            except Exception:
                pass

    async def launch(self, interaction: discord.Interaction) -> None:
        session = await self.sessions.load(interaction.channel.id, interaction.user.id)
        await self._send_or_edit_panel(interaction, session)

    async def restart(self, interaction: discord.Interaction) -> None:
        session = await self.sessions.load(interaction.channel.id, interaction.user.id)
        if hasattr(session, "reset"):
            session.reset()
        await self._send_or_edit_panel(interaction, session)
