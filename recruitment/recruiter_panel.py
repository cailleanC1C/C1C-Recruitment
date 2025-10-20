"""Recruiter panel command restored from the legacy Matchmaker bot.

This module provides a text-only implementation of the `!clanmatch` panel that
mirrors the legacy filters while skipping crest rendering for mobile
performance.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional, Sequence, Tuple

import discord
from discord.ext import commands
from discord import InteractionResponded

from recruitment import cards
from sheets import recruitment as recruitment_sheets
from shared import config
from shared.coreops_rbac import is_admin_member, is_recruiter

log = logging.getLogger(__name__)

PAGE_SIZE = 10

# Column indices (0-based) sourced from the legacy Sheets schema.
COL_B_CLAN = 1
COL_C_TAG = 2
COL_E_SPOTS = 4

COL_P_CB = 15
COL_Q_HYDRA = 16
COL_R_CHIMERA = 17
COL_S_CVC = 18
COL_T_SIEGE = 19
COL_U_STYLE = 20

IDX_V = 21
IDX_W = 22
IDX_X = 23
IDX_Y = 24
IDX_Z = 25
IDX_AA = 26
IDX_AB = 27
IDX_AC_RESERVED = 28
IDX_AD_COMMENTS = 29
IDX_AE_REQUIREMENTS = 30
IDX_AF_INACTIVES = 31

CB_CHOICES = ["Easy", "Normal", "Hard", "Brutal", "NM", "UNM"]
HYDRA_CHOICES = ["Normal", "Hard", "Brutal", "Nightmare"]
CHIMERA_CHOICES = ["Normal", "Hard", "Brutal", "Nightmare"]
PLAYSTYLE_CHOICES = ["Stress Free", "Casual", "Semi Competitive", "Competitive"]

TOKEN_MAP = {
    "EASY": "ESY",
    "NORMAL": "NML",
    "HARD": "HRD",
    "BRUTAL": "BTL",
    "NM": "NM",
    "UNM": "UNM",
    "ULTRA-NIGHTMARE": "UNM",
}

STYLE_CANON = {
    "STRESS FREE": "STRESSFREE",
    "STRESS-FREE": "STRESSFREE",
    "STRESSFREE": "STRESSFREE",
    "CASUAL": "CASUAL",
    "SEMI COMPETITIVE": "SEMICOMPETITIVE",
    "SEMI-COMPETITIVE": "SEMICOMPETITIVE",
    "SEMICOMPETITIVE": "SEMICOMPETITIVE",
    "COMPETITIVE": "COMPETITIVE",
}


def _norm(value: str) -> str:
    return (value or "").strip().upper()


def _is_header_row(row: Sequence[str]) -> bool:
    clan = _norm(row[COL_B_CLAN]) if len(row) > COL_B_CLAN else ""
    tag = _norm(row[COL_C_TAG]) if len(row) > COL_C_TAG else ""
    spots = _norm(row[COL_E_SPOTS]) if len(row) > COL_E_SPOTS else ""
    return clan in {"CLAN", "CLAN NAME"} or tag == "TAG" or spots == "SPOTS"


def _map_token(choice: str) -> str:
    mapped = TOKEN_MAP.get(_norm(choice))
    return mapped if mapped is not None else _norm(choice)


def _cell_has_diff(cell_text: str, token: str | None) -> bool:
    if not token:
        return True
    mapped = _map_token(token)
    cell = _norm(cell_text)
    if mapped in cell:
        return True
    if mapped == "HRD" and "HARD" in cell:
        return True
    if mapped == "NML" and "NORMAL" in cell:
        return True
    if mapped == "BTL" and "BRUTAL" in cell:
        return True
    return False


def _cell_equals_flag(cell_text: str, expected: Optional[str]) -> bool:
    if expected is None:
        return True
    return (cell_text or "").strip() == expected


def _canon_style(value: str) -> Optional[str]:
    if not value:
        return None
    text = value.replace("-", " ")
    text = " ".join(text.split()).upper()
    if text in STYLE_CANON:
        return STYLE_CANON[text]
    if text == "SEMI COMPETITIVE":
        return "SEMICOMPETITIVE"
    if text == "STRESS FREE":
        return "STRESSFREE"
    return text if text in {"STRESSFREE", "CASUAL", "SEMICOMPETITIVE", "COMPETITIVE"} else None


def _split_styles(cell_text: str) -> set[str]:
    import re

    tokens = re.split(r"[,\|/;]+", cell_text or "")
    values: set[str] = set()
    for token in tokens:
        canon = _canon_style(token)
        if canon:
            values.add(canon)
    return values


def _playstyle_ok(cell_text: str, wanted: Optional[str]) -> bool:
    if not wanted:
        return True
    canon = _canon_style(wanted)
    if not canon:
        return True
    return canon in _split_styles(cell_text)


def _parse_number(cell_text: str) -> int:
    import re

    match = re.search(r"\d+", cell_text or "")
    return int(match.group()) if match else 0


def _row_matches(
    row: Sequence[str],
    cb: Optional[str],
    hydra: Optional[str],
    chimera: Optional[str],
    cvc: Optional[str],
    siege: Optional[str],
    playstyle: Optional[str],
) -> bool:
    if len(row) <= IDX_AB:
        return False
    if _is_header_row(row):
        return False
    if not (row[COL_B_CLAN] or "").strip():
        return False
    return (
        _cell_has_diff(row[COL_P_CB], cb)
        and _cell_has_diff(row[COL_Q_HYDRA], hydra)
        and _cell_has_diff(row[COL_R_CHIMERA], chimera)
        and _cell_equals_flag(row[COL_S_CVC], cvc)
        and _cell_equals_flag(row[COL_T_SIEGE], siege)
        and _playstyle_ok(row[COL_U_STYLE], playstyle)
    )


def _format_filters_footer(
    cb: Optional[str],
    hydra: Optional[str],
    chimera: Optional[str],
    cvc: Optional[str],
    siege: Optional[str],
    playstyle: Optional[str],
    roster_mode: Optional[str],
) -> str:
    parts: list[str] = []
    if cb:
        parts.append(f"CB: {cb}")
    if hydra:
        parts.append(f"Hydra: {hydra}")
    if chimera:
        parts.append(f"Chimera: {chimera}")
    if cvc is not None:
        parts.append(f"CvC: {'Yes' if cvc == '1' else 'No'}")
    if siege is not None:
        parts.append(f"Siege: {'Yes' if siege == '1' else 'No'}")
    if playstyle:
        parts.append(f"Playstyle: {playstyle}")

    roster_label = "All"
    if roster_mode == "open":
        roster_label = "Open only"
    elif roster_mode == "inactives":
        roster_label = "Inactives only"
    elif roster_mode == "full":
        roster_label = "Full only"
    parts.append(f"Roster: {roster_label}")
    return " • ".join(parts)


def _page_embeds(
    rows: Sequence[Sequence[str]],
    page_index: int,
    filters_text: str,
) -> list[discord.Embed]:
    start = page_index * PAGE_SIZE
    end = min(len(rows), start + PAGE_SIZE)
    embeds = [
        cards.make_embed_for_row_classic(
            row,
            filters_text,
            include_crest=False,
        )
        for row in rows[start:end]
    ]
    if embeds:
        total_pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
        page_info = f"Page {page_index + 1}/{total_pages} • {len(rows)} total"
        last = embeds[-1]
        footer_text = last.footer.text or ""
        last.set_footer(text=f"{footer_text} • {page_info}" if footer_text else page_info)
    return embeds


class RecruiterPanelView(discord.ui.View):
    """Interactive filter panel for recruiter searches."""

    DEFAULT_STATUS = "Pick filters and press **Search Clans** to fetch clans."

    def __init__(self, cog: "RecruiterPanelCog", author_id: int) -> None:
        super().__init__(timeout=1800)
        self.cog = cog
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

        self.cb: Optional[str] = None
        self.hydra: Optional[str] = None
        self.chimera: Optional[str] = None
        self.playstyle: Optional[str] = None
        self.cvc: Optional[str] = None
        self.siege: Optional[str] = None
        self.roster_mode: Optional[str] = "open"

        self.matches: list[Sequence[str]] = []
        self.results_filters_text: str = ""
        self.total_found: int = 0
        self.page: int = 0
        self.results_stale: bool = False
        self.status_message: str = self.DEFAULT_STATUS

        self._build_components()
        self._reset_filters()

    def _build_components(self) -> None:
        cb_select = discord.ui.Select(
            placeholder="CB Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label=label, value=label) for label in CB_CHOICES],
            custom_id="rp_cb",
        )
        cb_select.callback = self._on_cb_select
        self.add_item(cb_select)
        self.cb_select = cb_select  # type: ignore[attr-defined]

        hydra_select = discord.ui.Select(
            placeholder="Hydra Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label=label, value=label) for label in HYDRA_CHOICES],
            custom_id="rp_hydra",
        )
        hydra_select.callback = self._on_hydra_select
        self.add_item(hydra_select)
        self.hydra_select = hydra_select  # type: ignore[attr-defined]

        chimera_select = discord.ui.Select(
            placeholder="Chimera Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=label) for label in CHIMERA_CHOICES
            ],
            custom_id="rp_chimera",
        )
        chimera_select.callback = self._on_chimera_select
        self.add_item(chimera_select)
        self.chimera_select = chimera_select  # type: ignore[attr-defined]

        playstyle_select = discord.ui.Select(
            placeholder="Playstyle (optional)",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=label)
                for label in PLAYSTYLE_CHOICES
            ],
            custom_id="rp_style",
        )
        playstyle_select.callback = self._on_playstyle_select
        self.add_item(playstyle_select)
        self.playstyle_select = playstyle_select  # type: ignore[attr-defined]

        cvc_button = discord.ui.Button(
            label="CvC: —",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_cvc",
        )
        cvc_button.callback = self._on_cvc_toggle
        self.add_item(cvc_button)
        self.cvc_button = cvc_button  # type: ignore[attr-defined]

        siege_button = discord.ui.Button(
            label="Siege: —",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_siege",
        )
        siege_button.callback = self._on_siege_toggle
        self.add_item(siege_button)
        self.siege_button = siege_button  # type: ignore[attr-defined]

        roster_button = discord.ui.Button(
            label="Open Spots Only",
            style=discord.ButtonStyle.success,
            custom_id="rp_roster",
        )
        roster_button.callback = self._on_roster_toggle
        self.add_item(roster_button)
        self.roster_button = roster_button  # type: ignore[attr-defined]

        reset_button = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_reset",
        )
        reset_button.callback = self._on_reset
        self.add_item(reset_button)

        search_button = discord.ui.Button(
            label="Search Clans",
            style=discord.ButtonStyle.primary,
            custom_id="rp_search",
        )
        search_button.callback = self._on_search
        self.add_item(search_button)

        prev_button = discord.ui.Button(
            label="◀ Prev Page",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_prev",
        )
        prev_button.callback = self._on_prev_page
        self.add_item(prev_button)
        self.prev_button = prev_button  # type: ignore[attr-defined]

        next_button = discord.ui.Button(
            label="Next Page ▶",
            style=discord.ButtonStyle.primary,
            custom_id="rp_next",
        )
        next_button.callback = self._on_next_page
        self.add_item(next_button)
        self.next_button = next_button  # type: ignore[attr-defined]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
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
            except Exception:  # pragma: no cover - defensive followup
                pass
        return False

    def _sync_visuals(self) -> None:
        for option in self.cb_select.options:
            option.default = option.value == self.cb
        for option in self.hydra_select.options:
            option.default = option.value == self.hydra
        for option in self.chimera_select.options:
            option.default = option.value == self.chimera
        for option in self.playstyle_select.options:
            option.default = option.value == self.playstyle

        def label_for_toggle(name: str, value: Optional[str]) -> str:
            state = "—" if value is None else ("Yes" if value == "1" else "No")
            return f"{name}: {state}"

        self.cvc_button.label = label_for_toggle("CvC", self.cvc)
        self.cvc_button.style = (
            discord.ButtonStyle.success
            if self.cvc == "1"
            else discord.ButtonStyle.danger
            if self.cvc == "0"
            else discord.ButtonStyle.secondary
        )

        self.siege_button.label = label_for_toggle("Siege", self.siege)
        self.siege_button.style = (
            discord.ButtonStyle.success
            if self.siege == "1"
            else discord.ButtonStyle.danger
            if self.siege == "0"
            else discord.ButtonStyle.secondary
        )

        if self.roster_mode == "open":
            self.roster_button.label = "Open Spots Only"
            self.roster_button.style = discord.ButtonStyle.success
        elif self.roster_mode == "inactives":
            self.roster_button.label = "Inactives Only"
            self.roster_button.style = discord.ButtonStyle.danger
        elif self.roster_mode == "full":
            self.roster_button.label = "Full Only"
            self.roster_button.style = discord.ButtonStyle.primary
        else:
            self.roster_button.label = "Any Roster"
            self.roster_button.style = discord.ButtonStyle.secondary

        max_page = max(0, math.ceil(len(self.matches) / PAGE_SIZE) - 1)
        self.prev_button.disabled = not self.matches or self.page <= 0
        self.next_button.disabled = not self.matches or self.page >= max_page

    def _reset_filters(self, *, for_user: bool = False) -> None:
        self.cb = self.hydra = self.chimera = self.playstyle = None
        self.cvc = self.siege = None
        self.roster_mode = "open"
        self.matches = []
        self.results_filters_text = ""
        self.total_found = 0
        self.page = 0
        self.results_stale = False
        self.status_message = (
            "Filters reset. Pick filters and press **Search Clans** to fetch clans."
            if for_user
            else self.DEFAULT_STATUS
        )
        self._sync_visuals()

    def _mark_filters_changed(self) -> None:
        if self.matches:
            self.results_stale = True
            self.status_message = (
                "Filters changed. Press **Search Clans** to refresh your results."
            )
        else:
            self.status_message = self.DEFAULT_STATUS
        self.page = 0
        self._sync_visuals()

    async def _build_page(self) -> Tuple[list[discord.Embed], list[discord.File]]:
        description_lines = []
        if self.status_message:
            description_lines.append(self.status_message)
        if self.results_stale and self.matches:
            description_lines.append(
                "⚠️ The clan list reflects your **last** search. Press **Search Clans** to refresh."
            )
        description_lines.append(
            "Pick any filters (*you can leave some blank*) and click **Search Clans**.\n"
            "ℹ️ Choose the most important criteria for your recruit — too many filters might narrow things down to zero.\n"
            "ℹ️ Click **Open Spots Only** to cycle roster filters."
        )
        embed = discord.Embed(
            title="Find a C1C Clan for your recruit",
            description="\n\n".join(description_lines),
        )
        embed.set_footer(text="Only the summoner can use this panel.")

        active_filters = _format_filters_footer(
            self.cb,
            self.hydra,
            self.chimera,
            self.cvc,
            self.siege,
            self.playstyle,
            self.roster_mode,
        )
        if active_filters:
            embed.add_field(name="Active filters", value=active_filters, inline=False)

        if self.matches and self.total_found > len(self.matches):
            embed.add_field(
                name="Results note",
                value=f"Showing first {len(self.matches)} of {self.total_found} clans.",
                inline=False,
            )

        embeds = [embed]
        if self.matches:
            filters_text = self.results_filters_text or active_filters
            embeds.extend(_page_embeds(self.matches, self.page, filters_text or ""))
        return embeds, []

    async def _on_cb_select(self, interaction: discord.Interaction) -> None:
        self.cb = self.cb_select.values[0] if self.cb_select.values else None
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_hydra_select(self, interaction: discord.Interaction) -> None:
        self.hydra = self.hydra_select.values[0] if self.hydra_select.values else None
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_chimera_select(self, interaction: discord.Interaction) -> None:
        self.chimera = (
            self.chimera_select.values[0] if self.chimera_select.values else None
        )
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_playstyle_select(self, interaction: discord.Interaction) -> None:
        self.playstyle = (
            self.playstyle_select.values[0] if self.playstyle_select.values else None
        )
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    @staticmethod
    def _cycle_toggle(current: Optional[str]) -> Optional[str]:
        if current is None:
            return "1"
        if current == "1":
            return "0"
        return None

    async def _on_cvc_toggle(self, interaction: discord.Interaction) -> None:
        self.cvc = self._cycle_toggle(self.cvc)
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_siege_toggle(self, interaction: discord.Interaction) -> None:
        self.siege = self._cycle_toggle(self.siege)
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_roster_toggle(self, interaction: discord.Interaction) -> None:
        if self.roster_mode == "open":
            self.roster_mode = "inactives"
        elif self.roster_mode == "inactives":
            self.roster_mode = "full"
        elif self.roster_mode == "full":
            self.roster_mode = None
        else:
            self.roster_mode = "open"
        self._mark_filters_changed()
        await interaction.response.defer_update()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_reset(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer_update()
        self._reset_filters(for_user=True)
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)
        try:
            await interaction.followup.send("Filters reset ✓", ephemeral=True)
        except Exception:
            pass

    async def _on_search(self, interaction: discord.Interaction) -> None:
        if not any(
            [
                self.cb,
                self.hydra,
                self.chimera,
                self.cvc,
                self.siege,
                self.playstyle,
                self.roster_mode is not None,
            ]
        ):
            await interaction.response.send_message(
                "Pick at least **one** filter, then try again. 🙂",
                ephemeral=True,
            )
            return

        await interaction.response.defer_update()

        try:
            rows = recruitment_sheets.fetch_clans(force=False)
        except Exception as exc:  # pragma: no cover - defensive guard
            log.exception("failed to fetch clan rows", exc_info=exc)
            if self.matches:
                self.results_stale = True
            self._sync_visuals()
            self.status_message = (
                "⚠️ I couldn’t load the clan roster. Try again in a moment."
            )
            embeds, _ = await self._build_page()
            await interaction.message.edit(embeds=embeds, view=self)
            try:
                await interaction.followup.send(
                    "⚠️ I couldn’t load the clan roster. Try again in a moment.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        matches: list[Sequence[str]] = []
        for row in rows[1:]:
            try:
                if not _row_matches(
                    row,
                    self.cb,
                    self.hydra,
                    self.chimera,
                    self.cvc,
                    self.siege,
                    self.playstyle,
                ):
                    continue
                spots = _parse_number(row[COL_E_SPOTS] if len(row) > COL_E_SPOTS else "")
                inactives = _parse_number(
                    row[IDX_AF_INACTIVES] if len(row) > IDX_AF_INACTIVES else ""
                )
                if self.roster_mode == "open" and spots <= 0:
                    continue
                if self.roster_mode == "full" and spots > 0:
                    continue
                if self.roster_mode == "inactives" and inactives <= 0:
                    continue
                matches.append(row)
            except Exception:
                continue

        if not matches:
            self.matches = []
            self.results_filters_text = _format_filters_footer(
                self.cb,
                self.hydra,
                self.chimera,
                self.cvc,
                self.siege,
                self.playstyle,
                self.roster_mode,
            )
            self.total_found = 0
            self.results_stale = False
            self.status_message = (
                "No matching clans found. Try again with fewer or different filters."
            )
            self._sync_visuals()
            embeds, _ = await self._build_page()
            await interaction.message.edit(embeds=embeds, view=self)
            return

        cap = max(1, config.get_search_results_soft_cap(25))
        total_found = len(matches)
        if total_found > cap:
            matches = matches[:cap]
        cap_note = f"first {cap} of {total_found}" if total_found > cap else None

        filters_text = _format_filters_footer(
            self.cb,
            self.hydra,
            self.chimera,
            self.cvc,
            self.siege,
            self.playstyle,
            self.roster_mode,
        )
        if cap_note:
            filters_text = f"{filters_text} • {cap_note}" if filters_text else cap_note

        self.matches = matches
        self.results_filters_text = filters_text
        self.total_found = total_found
        self.page = 0
        self.results_stale = False
        self.status_message = (
            f"Showing first {len(matches)} of {total_found} clans." if cap_note else f"Found {total_found} matching clans."
        )
        self._sync_visuals()

        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)
        try:
            await interaction.followup.send("Search results updated ✓", ephemeral=True)
        except Exception:
            pass

    async def _on_prev_page(self, interaction: discord.Interaction) -> None:
        if not self.matches:
            return
        await interaction.response.defer_update()
        if self.page > 0:
            self.page -= 1
        self._sync_visuals()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def _on_next_page(self, interaction: discord.Interaction) -> None:
        if not self.matches:
            return
        await interaction.response.defer_update()
        max_page = max(0, math.ceil(len(self.matches) / PAGE_SIZE) - 1)
        if self.page < max_page:
            self.page += 1
        self._sync_visuals()
        embeds, _ = await self._build_page()
        await interaction.message.edit(embeds=embeds, view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                expired = discord.Embed(
                    title="Find a C1C Clan",
                    description="⏳ This panel expired. Type **!clanmatch** to open a fresh one.",
                )
                await self.message.edit(embeds=[expired], view=self)
            except Exception:  # pragma: no cover - best effort
                pass
        if self.message:
            self.cog.unregister_panel(self.message.id)


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

    @commands.command(name="clanmatch")
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def clanmatch(self, ctx: commands.Context, *, extra: Optional[str] = None) -> None:
        """Open the recruiter panel to find clans for a recruit."""

        if extra and extra.strip():
            message = (
                "❌ `!clanmatch` doesn’t take a clan tag or name.\n"
                "• Use **`!clan <tag or name>`** to see a specific clan profile (e.g., `!clan C1CE`).\n"
                "• Or type **`!clanmatch`** by itself to open the filter panel."
            )
            await ctx.reply(message, mention_author=False)
            return

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

        existing_panel = self._panel_for_owner(ctx.author.id)
        if existing_panel:
            channel_id, message_id = existing_panel
            channel = ctx.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await ctx.bot.fetch_channel(channel_id)
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

        thread = None
        try:
            from shared import config as _cfg

            mode = getattr(_cfg, "get_panel_thread_mode", lambda: "channel")()
            fixed_id = getattr(_cfg, "get_panel_fixed_thread_id", lambda: None)()
            if str(mode).lower() == "fixed" and fixed_id:
                thread = ctx.guild.get_thread(int(fixed_id)) if ctx.guild else None
                if not thread and ctx.bot:
                    thread = await ctx.bot.fetch_channel(int(fixed_id))
                if isinstance(thread, discord.Thread) and thread.archived:
                    try:
                        await thread.edit(archived=False)
                    except Exception:
                        pass
        except Exception:
            thread = None

        target: discord.abc.MessageableChannel = (
            thread if (thread and hasattr(thread, "send")) else ctx.channel
        )
        sent = await target.send(embeds=embeds, view=view)
        view.message = sent
        self.register_panel(
            message_id=sent.id,
            owner_id=ctx.author.id,
            channel_id=sent.channel.id,
        )

        if target is not ctx.channel:
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
    await bot.add_cog(RecruiterPanelCog(bot))
