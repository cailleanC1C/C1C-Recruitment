"""Standalone view for paginating recruiter panel results."""

from __future__ import annotations

import contextlib
from typing import Protocol

import discord
from discord import InteractionResponded


class ResultsPagerCallbacks(Protocol):
    """Interface implemented by the recruiter panel for pager updates."""

    @property
    def owner_id(self) -> int:  # pragma: no cover - protocol definition
        ...

    @property
    def current_page(self) -> int:  # pragma: no cover - protocol definition
        ...

    @property
    def total_pages(self) -> int:  # pragma: no cover - protocol definition
        ...

    async def on_prev_page(  # pragma: no cover - protocol definition
        self, interaction: discord.Interaction
    ) -> None:
        ...

    async def on_next_page(  # pragma: no cover - protocol definition
        self, interaction: discord.Interaction
    ) -> None:
        ...


class ResultsPagerView(discord.ui.View):
    """Prev/Next pager bound to the recruiter results message."""

    def __init__(
        self, callbacks: ResultsPagerCallbacks, *, timeout: float | None = 1800
    ) -> None:
        super().__init__(timeout=timeout)
        self.callbacks = callbacks
        self.message: discord.Message | None = None

        prev_button = discord.ui.Button(
            label="◀ Prev Page",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_results_prev",
            row=0,
        )
        prev_button.callback = self._handle_prev
        self.add_item(prev_button)
        self.prev_button = prev_button

        next_button = discord.ui.Button(
            label="Next Page ▶",
            style=discord.ButtonStyle.primary,
            custom_id="rp_results_next",
            row=0,
        )
        next_button.callback = self._handle_next
        self.add_item(next_button)
        self.next_button = next_button

        self.sync_state()

    def bind_to(self, message: discord.Message) -> None:
        """Remember which message currently owns the pager."""

        self.message = message

    def sync_state(self) -> None:
        """Enable/disable buttons based on current paging metadata."""

        total = self.callbacks.total_pages
        if total <= 1:
            self.prev_button.disabled = True
            self.next_button.disabled = True
            return

        self.prev_button.disabled = self.callbacks.current_page <= 0
        self.next_button.disabled = self.callbacks.current_page >= total - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.callbacks.owner_id:
            return True
        try:
            await interaction.response.send_message(
                "⚠️ Not your panel. Type **!clanmatch** to summon your own.",
                ephemeral=True,
            )
        except InteractionResponded:
            with contextlib.suppress(Exception):
                await interaction.followup.send(
                    "⚠️ Not your panel. Type **!clanmatch** to summon your own.",
                    ephemeral=True,
                )
        return False

    async def _handle_prev(self, interaction: discord.Interaction) -> None:
        await self.callbacks.on_prev_page(interaction)
        self.sync_state()

    async def _handle_next(self, interaction: discord.Interaction) -> None:
        await self.callbacks.on_next_page(interaction)
        self.sync_state()

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            with contextlib.suppress(Exception):
                await self.message.edit(view=self)
