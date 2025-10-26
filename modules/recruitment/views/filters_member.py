"""Legacy member-panel filter controls reused for the restored clan search."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import discord
from discord import InteractionResponded

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .member_panel_legacy import MemberPanelControllerLegacy, MemberPanelState


CB_CHOICES = ["Easy", "Normal", "Hard", "Brutal", "NM", "UNM"]
HYDRA_CHOICES = ["Normal", "Hard", "Brutal", "NM"]
CHIMERA_CHOICES = ["Easy", "Normal", "Hard", "Brutal", "NM", "UNM"]
PLAYSTYLE_CHOICES = ["stress-free", "Casual", "Semi Competitive", "Competitive"]


class _FilterSelect(discord.ui.Select):
    """Single-value select that updates a ``MemberFiltersView`` field."""

    def __init__(
        self,
        *,
        field: str,
        placeholder: str,
        options: list[str],
        row: int,
    ) -> None:
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=1,
            row=row,
            options=[discord.SelectOption(label=value, value=value) for value in options],
        )
        self._field = field

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - exercised indirectly
        view = cast("MemberFiltersView", self.view)
        value = self.values[0] if self.values else None
        await view.apply_changes(interaction, **{self._field: value})


class MemberFiltersView(discord.ui.View):
    """Stacked dropdowns with legacy toggle buttons for the member search."""

    def __init__(
        self,
        *,
        controller: "MemberPanelControllerLegacy",
        state: "MemberPanelState",
        timeout: float = 900,
    ) -> None:
        super().__init__(timeout=timeout)
        self.controller = controller
        self.state = state
        self.message: discord.Message | None = None
        self._install_components()
        self._sync_visuals()

    # ------------------------------------------------------------------
    # Discord view plumbing
    # ------------------------------------------------------------------
    def bind_to_message(self, message: discord.Message) -> None:
        self.message = message
        self._sync_visuals()

    @property
    def panel_message_id(self) -> int | None:
        if self.message is None:
            return None
        return getattr(self.message, "id", None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.state.author_id:
            return True
        note = "⚠️ Not your panel. Type **!clansearch** to open your own."
        try:
            await interaction.response.send_message(note, ephemeral=True)
        except InteractionResponded:
            try:
                await interaction.followup.send(note, ephemeral=True)
            except Exception:  # pragma: no cover - defensive guard
                pass
        return False

    async def on_timeout(self) -> None:  # pragma: no cover - runtime safety
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Component factories
    # ------------------------------------------------------------------
    def _install_components(self) -> None:
        self.cb_select = _FilterSelect(
            field="cb",
            placeholder="CB Difficulty (optional)",
            options=CB_CHOICES,
            row=0,
        )
        self.add_item(self.cb_select)

        self.hydra_select = _FilterSelect(
            field="hydra",
            placeholder="Hydra Difficulty (optional)",
            options=HYDRA_CHOICES,
            row=1,
        )
        self.add_item(self.hydra_select)

        self.chimera_select = _FilterSelect(
            field="chimera",
            placeholder="Chimera Difficulty (optional)",
            options=CHIMERA_CHOICES,
            row=2,
        )
        self.add_item(self.chimera_select)

        self.playstyle_select = _FilterSelect(
            field="playstyle",
            placeholder="Playstyle (optional)",
            options=PLAYSTYLE_CHOICES,
            row=3,
        )
        self.add_item(self.playstyle_select)

        self.cvc_button = discord.ui.Button(
            label="CvC: —",
            style=discord.ButtonStyle.secondary,
            row=4,
            custom_id="mf_cvc",
        )
        self.cvc_button.callback = self._handle_cvc  # type: ignore[assignment]
        self.add_item(self.cvc_button)

        self.siege_button = discord.ui.Button(
            label="Siege: —",
            style=discord.ButtonStyle.secondary,
            row=4,
            custom_id="mf_siege",
        )
        self.siege_button.callback = self._handle_siege  # type: ignore[assignment]
        self.add_item(self.siege_button)

        self.roster_button = discord.ui.Button(
            label="Open Spots Only",
            style=discord.ButtonStyle.success,
            row=4,
            custom_id="mf_roster",
        )
        self.roster_button.callback = self._handle_roster  # type: ignore[assignment]
        self.add_item(self.roster_button)

        self.reset_button = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.secondary,
            row=4,
            custom_id="mf_reset",
        )
        self.reset_button.callback = self._handle_reset  # type: ignore[assignment]
        self.add_item(self.reset_button)

        self.search_button = discord.ui.Button(
            label="Search Clans",
            style=discord.ButtonStyle.primary,
            row=4,
            custom_id="mf_search",
        )
        self.search_button.callback = self._handle_search  # type: ignore[assignment]
        self.add_item(self.search_button)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    async def apply_changes(self, interaction: discord.Interaction, **changes) -> None:
        self.state = self.state.with_updates(**changes)
        panel_id = self.panel_message_id
        if panel_id is not None:
            self.controller.update_panel_state(panel_id, self.state)
        self._sync_visuals()
        await self._edit_panel(interaction)

    async def _handle_cvc(self, interaction: discord.Interaction) -> None:
        await self.apply_changes(interaction, cvc=self._cycle_flag(self.state.cvc))

    async def _handle_siege(self, interaction: discord.Interaction) -> None:
        await self.apply_changes(interaction, siege=self._cycle_flag(self.state.siege))

    async def _handle_roster(self, interaction: discord.Interaction) -> None:
        next_value = self._cycle_roster(self.state.roster_mode)
        await self.apply_changes(interaction, roster_mode=next_value)

    async def _handle_reset(self, interaction: discord.Interaction) -> None:
        await self.controller.on_reset(interaction, self)

    async def _handle_search(self, interaction: discord.Interaction) -> None:
        await self.controller.on_search(interaction, self)

    def set_state(self, state: "MemberPanelState") -> None:
        self.state = state
        self._sync_visuals()

    def _sync_visuals(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                chosen = None
                placeholder = (child.placeholder or "")
                if "CB Difficulty" in placeholder:
                    chosen = self.state.cb
                elif "Hydra Difficulty" in placeholder:
                    chosen = self.state.hydra
                elif "Chimera Difficulty" in placeholder:
                    chosen = self.state.chimera
                elif "Playstyle" in placeholder:
                    chosen = self.state.playstyle
                for option in child.options:
                    option.default = bool(chosen and option.value == chosen)
            elif isinstance(child, discord.ui.Button):
                if child.custom_id == "mf_cvc":
                    label, style = self._toggle_label("CvC", self.state.cvc)
                    child.label = label
                    child.style = style
                elif child.custom_id == "mf_siege":
                    label, style = self._toggle_label("Siege", self.state.siege)
                    child.label = label
                    child.style = style
                elif child.custom_id == "mf_roster":
                    label, style = self._roster_visual(self.state.roster_mode)
                    child.label = label
                    child.style = style

    async def _edit_panel(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.edit_message(view=self)
        except InteractionResponded:
            try:
                if interaction.message is not None:
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        view=self,
                    )
            except Exception:  # pragma: no cover - defensive guard
                pass

    # ------------------------------------------------------------------
    # Legacy toggle semantics
    # ------------------------------------------------------------------
    @staticmethod
    def _cycle_flag(current: str | None) -> str | None:
        if current is None:
            return "1"
        if current == "1":
            return "0"
        return None

    @staticmethod
    def _cycle_roster(current: str | None) -> str | None:
        order = ["open", "inactives", "full", None]
        if current not in order:
            return "open"
        idx = order.index(current) + 1
        if idx >= len(order):
            idx = 0
        return order[idx]

    @staticmethod
    def _toggle_label(name: str, value: str | None) -> tuple[str, discord.ButtonStyle]:
        if value == "1":
            return f"{name}: Yes", discord.ButtonStyle.success
        if value == "0":
            return f"{name}: No", discord.ButtonStyle.danger
        return f"{name}: —", discord.ButtonStyle.secondary

    @staticmethod
    def _roster_visual(value: str | None) -> tuple[str, discord.ButtonStyle]:
        if value == "open":
            return "Open Spots Only", discord.ButtonStyle.success
        if value == "inactives":
            return "Inactives Only", discord.ButtonStyle.danger
        if value == "full":
            return "Full Only", discord.ButtonStyle.primary
        return "Any Roster", discord.ButtonStyle.secondary


__all__ = ["MemberFiltersView"]
