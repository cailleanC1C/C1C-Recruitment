"""Legacy member-panel filter controls reused for the restored clan search."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .member_panel_legacy import MemberPanelControllerLegacy, MemberPanelState


CB_CHOICES = ["Easy", "Normal", "Hard", "Brutal", "NM", "UNM"]
HYDRA_CHOICES = ["Normal", "Hard", "Brutal", "Nightmare"]
CHIMERA_CHOICES = ["Normal", "Hard", "Brutal", "Nightmare", "UltraNightmare"]
PLAYSTYLE_CHOICES = ["Stress Free", "Casual", "Semi Competitive", "Competitive"]


class MemberFiltersRow:
    """Mixin that mounts legacy filter controls onto a Discord view."""

    controller: "MemberPanelControllerLegacy"
    state: "MemberPanelState"

    def __init__(
        self,
        *,
        controller: "MemberPanelControllerLegacy",
        state: "MemberPanelState",
    ) -> None:
        self.controller = controller
        self.state = state
        self._install_filter_components()
        self._sync_filter_labels()

    async def _dispatch_filter_change(
        self, interaction: discord.Interaction
    ) -> None:
        new_state = self.state.with_updates(page=0)
        await self.controller.refresh_from_filters(interaction, new_state)

    def _install_filter_components(self) -> None:
        cb_button = discord.ui.Button(
            label="CB: —",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_cb",
            row=0,
        )
        cb_button.callback = self._handle_cb  # type: ignore[assignment]
        self.add_item(cb_button)
        self.cb_button = cb_button

        hydra_button = discord.ui.Button(
            label="Hydra: —",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_hydra",
            row=0,
        )
        hydra_button.callback = self._handle_hydra  # type: ignore[assignment]
        self.add_item(hydra_button)
        self.hydra_button = hydra_button

        chimera_button = discord.ui.Button(
            label="Chimera: —",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_chimera",
            row=0,
        )
        chimera_button.callback = self._handle_chimera  # type: ignore[assignment]
        self.add_item(chimera_button)
        self.chimera_button = chimera_button

        playstyle_button = discord.ui.Button(
            label="Playstyle: —",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_playstyle",
            row=0,
        )
        playstyle_button.callback = self._handle_playstyle  # type: ignore[assignment]
        self.add_item(playstyle_button)
        self.playstyle_button = playstyle_button

        cvc_button = discord.ui.Button(
            label="CvC: Any",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_cvc",
            row=1,
        )
        cvc_button.callback = self._handle_cvc  # type: ignore[assignment]
        self.add_item(cvc_button)
        self.cvc_button = cvc_button

        siege_button = discord.ui.Button(
            label="Siege: Any",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_siege",
            row=1,
        )
        siege_button.callback = self._handle_siege  # type: ignore[assignment]
        self.add_item(siege_button)
        self.siege_button = siege_button

        roster_button = discord.ui.Button(
            label="Roster: Open",
            style=discord.ButtonStyle.success,
            custom_id="mf_roster",
            row=1,
        )
        roster_button.callback = self._handle_roster  # type: ignore[assignment]
        self.add_item(roster_button)
        self.roster_button = roster_button

        reset_button = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.secondary,
            custom_id="mf_reset",
            row=1,
        )
        reset_button.callback = self._handle_reset  # type: ignore[assignment]
        self.add_item(reset_button)
        self.reset_button = reset_button

    def _sync_filter_labels(self) -> None:
        self.cb_button.label = f"CB: {self.state.cb}" if self.state.cb else "CB: —"
        self.cb_button.style = (
            discord.ButtonStyle.primary if self.state.cb else discord.ButtonStyle.secondary
        )

        self.hydra_button.label = (
            f"Hydra: {self.state.hydra}" if self.state.hydra else "Hydra: —"
        )
        self.hydra_button.style = (
            discord.ButtonStyle.primary if self.state.hydra else discord.ButtonStyle.secondary
        )

        self.chimera_button.label = (
            f"Chimera: {self.state.chimera}" if self.state.chimera else "Chimera: —"
        )
        self.chimera_button.style = (
            discord.ButtonStyle.primary if self.state.chimera else discord.ButtonStyle.secondary
        )

        self.playstyle_button.label = (
            f"Playstyle: {self.state.playstyle}" if self.state.playstyle else "Playstyle: —"
        )
        self.playstyle_button.style = (
            discord.ButtonStyle.primary if self.state.playstyle else discord.ButtonStyle.secondary
        )

        def _toggle_label(value: str | None) -> tuple[str, discord.ButtonStyle]:
            if value == "1":
                return "Yes", discord.ButtonStyle.success
            if value == "0":
                return "No", discord.ButtonStyle.danger
            return "Any", discord.ButtonStyle.secondary

        label, style = _toggle_label(self.state.cvc)
        self.cvc_button.label = f"CvC: {label}"
        self.cvc_button.style = style

        label, style = _toggle_label(self.state.siege)
        self.siege_button.label = f"Siege: {label}"
        self.siege_button.style = style

        roster_styles = {
            "open": ("Open", discord.ButtonStyle.success),
            "inactives": ("Inactives", discord.ButtonStyle.danger),
            "full": ("Full", discord.ButtonStyle.primary),
            None: ("Any", discord.ButtonStyle.secondary),
        }
        roster_label, roster_style = roster_styles.get(self.state.roster_mode, ("Any", discord.ButtonStyle.secondary))
        self.roster_button.label = f"Roster: {roster_label}"
        self.roster_button.style = roster_style

    async def _handle_cb(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(cb=self._cycle(self.state.cb, CB_CHOICES), page=0)
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_hydra(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(
            hydra=self._cycle(self.state.hydra, HYDRA_CHOICES),
            page=0,
        )
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_chimera(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(
            chimera=self._cycle(self.state.chimera, CHIMERA_CHOICES),
            page=0,
        )
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_playstyle(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(
            playstyle=self._cycle(self.state.playstyle, PLAYSTYLE_CHOICES),
            page=0,
        )
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_cvc(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(cvc=self._cycle_flag(self.state.cvc), page=0)
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_siege(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(siege=self._cycle_flag(self.state.siege), page=0)
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_roster(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(
            roster_mode=self._cycle_roster(self.state.roster_mode),
            page=0,
        )
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    async def _handle_reset(self, interaction: discord.Interaction) -> None:
        self.state = self.state.with_updates(
            cb=None,
            hydra=None,
            chimera=None,
            playstyle=None,
            cvc=None,
            siege=None,
            roster_mode="open",
            page=0,
        )
        self._sync_filter_labels()
        await self._dispatch_filter_change(interaction)

    @staticmethod
    def _cycle(current: str | None, values: list[str]) -> str | None:
        if not values:
            return None
        if current not in values:
            return values[0]
        idx = values.index(current) + 1
        if idx >= len(values):
            return None
        return values[idx]

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
            return order[0]
        idx = order.index(current) + 1
        if idx >= len(order):
            idx = 0
        return order[idx]

