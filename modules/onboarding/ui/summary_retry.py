from __future__ import annotations

import logging
from typing import Any

import discord

from c1c_coreops import rbac
from modules.onboarding.session_store import store
from modules.onboarding.ui.summary_embed import build_summary_embed

log = logging.getLogger(__name__)


class RetryWelcomeSummaryView(discord.ui.View):
    def __init__(self, *, thread_id: int, timeout: float | None = 300) -> None:
        super().__init__(timeout=timeout)
        self.thread_id = thread_id
        self._retry_used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._retry_used:
            await interaction.response.send_message(
                "Summary has already been retried for this thread.",
                ephemeral=True,
            )
            return False
        if not rbac.is_recruiter(interaction.user):
            await interaction.response.send_message(
                "Only recruiters can retry the summary.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="🔁 Retry summary", style=discord.ButtonStyle.primary)
    async def retry_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[Any],
    ) -> None:
        thread = interaction.channel
        if not isinstance(thread, (discord.Thread, discord.TextChannel)):
            await interaction.response.send_message(
                "Cannot retry summary here — invalid channel context.",
                ephemeral=True,
            )
            return

        session = store.get(self.thread_id)
        if session is None:
            await interaction.response.send_message(
                "No onboarding answers found for this thread.",
                ephemeral=True,
            )
            return

        self._retry_used = True
        try:
            embed = build_summary_embed(
                flow="welcome",
                answers=session.answers,
                author=getattr(thread, "owner", None) or interaction.user,
                schema_hash=session.schema_hash,
                visibility=session.visibility,
            )
        except Exception:
            log.error(
                "onboarding.summary.retry_failed",
                exc_info=True,
                extra={"flow": "welcome", "thread_id": self.thread_id},
            )
            await interaction.response.send_message(
                "Couldn’t rebuild the summary. Please ping a bot admin.",
                ephemeral=True,
            )
            return

        store.end(self.thread_id)
        await interaction.response.edit_message(embed=embed, view=None)
