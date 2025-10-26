"""Legacy member search panel restored for ``!clansearch``."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

import discord
from discord import InteractionResponded
from discord.ext import commands

from ..search_helpers import (
    COL_E_SPOTS,
    IDX_AG_INACTIVES,
    format_filters_footer,
    parse_inactives_num,
    parse_spots_num,
    row_matches,
)
from .filters_member import MemberFiltersView
from .shared_member import MemberSearchPagedView
from shared import config as shared_config
from shared.sheets.async_facade import fetch_clans_async

log = logging.getLogger("c1c.recruitment.member.legacy")

ALLOWED_MENTIONS = discord.AllowedMentions.none()

PANEL_KEY_VARIANT = "search"

# Track active panel message per user (legacy behavior)
ACTIVE_PANELS: dict[tuple[int, str], int] = {}

_EMPTY_RESULTS_TEXT = (
    "No matching clans found. You might have set too many filter criteria — try again with fewer."
)


@dataclass
class MemberPanelState:
    """Snapshot of filter + view state for the legacy member panel."""

    author_id: int
    cb: str | None = None
    hydra: str | None = None
    chimera: str | None = None
    cvc: str | None = None
    siege: str | None = None
    playstyle: str | None = None
    roster_mode: str | None = "open"

    def copy(self) -> "MemberPanelState":
        return replace(self)

    def with_updates(self, **changes) -> "MemberPanelState":
        return replace(self, **changes)

    def any_filters(self) -> bool:
        return any(
            value is not None and str(value).strip()
            for value in (
                self.cb,
                self.hydra,
                self.chimera,
                self.cvc,
                self.siege,
                self.playstyle,
            )
        ) or self.roster_mode is not None


class MemberPanelControllerLegacy:
    """Restore the legacy new-message-per-search member clan search."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._panel_states: dict[int, MemberPanelState] = {}

    async def open(self, ctx: commands.Context) -> None:
        channel = getattr(ctx, "channel", None)
        author = getattr(ctx, "author", None)
        if channel is None or author is None:
            return

        author_id = getattr(author, "id", None)
        if author_id is None:
            return

        key = (int(author_id), PANEL_KEY_VARIANT)
        embed = self._build_intro_embed(author)

        existing_id = ACTIVE_PANELS.get(key)
        if existing_id:
            try:
                message = await channel.fetch_message(existing_id)
            except Exception:
                ACTIVE_PANELS.pop(key, None)
            else:
                state = self._panel_states.get(existing_id, MemberPanelState(author_id=author_id)).copy()
                view = MemberFiltersView(controller=self, state=state)
                view.bind_to_message(message)
                self._panel_states[message.id] = state
                try:
                    await message.edit(embed=embed, view=view)
                except discord.HTTPException:
                    log.exception("member panel reuse failed", extra={"message_id": message.id})
                return

        state = MemberPanelState(author_id=author_id)
        view = MemberFiltersView(controller=self, state=state)

        try:
            sent = await ctx.reply(embed=embed, view=view, mention_author=False)
        except discord.Forbidden as exc:
            log.warning("member panel send forbidden", exc_info=exc)
            await self._send_permission_fallback(ctx)
            return
        except discord.HTTPException as exc:
            log.exception("member panel send failed", exc_info=exc)
            return

        if isinstance(sent, discord.Message):
            view.bind_to_message(sent)
            self._panel_states[sent.id] = state
            ACTIVE_PANELS[key] = sent.id

    async def on_search(
        self,
        interaction: discord.Interaction,
        view: MemberFiltersView,
    ) -> None:
        state = view.state
        if not state.any_filters():
            await self._send_need_filter(interaction)
            return

        try:
            await interaction.response.defer(thinking=True)
        except InteractionResponded:
            pass

        rows = await self._load_rows()
        matches = self._filter_rows(rows, state)

        total_found = len(matches)
        soft_cap = max(1, shared_config.get_search_results_soft_cap(25))
        cap_note = None
        if total_found > soft_cap:
            matches = matches[:soft_cap]
            cap_note = f"first {soft_cap} of {total_found}"

        filters_text = format_filters_footer(
            state.cb,
            state.hydra,
            state.chimera,
            state.cvc,
            state.siege,
            state.playstyle,
            state.roster_mode,
            extra_note=cap_note,
        )

        empty_embed = discord.Embed(description=_EMPTY_RESULTS_TEXT)
        if filters_text:
            empty_embed.set_footer(text=f"Filters used: {filters_text}")

        results_view = MemberSearchPagedView(
            author_id=state.author_id,
            rows=matches,
            filters_text=filters_text,
            guild=interaction.guild,
            timeout=900,
            mode="lite",
            page=0,
            empty_embed=empty_embed,
        )
        results_view.state = state.copy()

        embeds, files = await results_view.build_outputs()
        if not embeds:
            embeds = [empty_embed]

        try:
            sent = await interaction.followup.send(
                embeds=embeds,
                files=files,
                view=results_view,
                allowed_mentions=ALLOWED_MENTIONS,
            )
        except discord.HTTPException as exc:
            log.exception("member results send failed", exc_info=exc)
            sent = None
        finally:
            _close_files(files)

        if isinstance(sent, discord.Message):
            results_view.bind_message(sent)

    async def on_reset(self, interaction: discord.Interaction, view: MemberFiltersView) -> None:
        new_state = MemberPanelState(author_id=view.state.author_id)
        view.set_state(new_state)
        panel_id = view.panel_message_id
        if panel_id is not None:
            self._panel_states[panel_id] = new_state
        try:
            await interaction.response.edit_message(view=view)
        except InteractionResponded:
            try:
                if interaction.message is not None:
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        view=view,
                    )
            except Exception:
                pass

    def update_panel_state(self, message_id: int | None, state: MemberPanelState) -> None:
        if message_id is None:
            return
        self._panel_states[message_id] = state

    async def _load_rows(self) -> Sequence[Sequence[str]]:
        try:
            rows = await fetch_clans_async(force=False)
        except Exception as exc:
            log.exception("member panel sheets fetch failed", exc_info=exc)
            return []
        return rows or []

    def _filter_rows(
        self, rows: Sequence[Sequence[str]], state: MemberPanelState
    ) -> list[Sequence[str]]:
        matches: list[Sequence[str]] = []
        for row in rows[1:]:  # skip headers
            try:
                if not row_matches(
                    row,
                    state.cb,
                    state.hydra,
                    state.chimera,
                    state.cvc,
                    state.siege,
                    state.playstyle,
                ):
                    continue

                spots_num = parse_spots_num(row[COL_E_SPOTS] if len(row) > COL_E_SPOTS else "")
                inactives_num = parse_inactives_num(
                    row[IDX_AG_INACTIVES] if len(row) > IDX_AG_INACTIVES else ""
                )

                if state.roster_mode == "open" and spots_num <= 0:
                    continue
                if state.roster_mode == "full" and spots_num > 0:
                    continue
                if state.roster_mode == "inactives" and inactives_num <= 0:
                    continue

                matches.append(row)
            except Exception:
                continue

        return matches

    async def _send_permission_fallback(self, ctx: commands.Context) -> None:
        message = (
            "⚠️ I need the **Embed Links** permission in this channel to show the clan search panel."
        )
        try:
            await ctx.send(message)
        except Exception:
            pass

    async def _send_need_filter(self, interaction: discord.Interaction) -> None:
        note = "Pick at least **one** filter, then try again. 🙂"
        try:
            await interaction.response.send_message(note, ephemeral=True)
        except InteractionResponded:
            try:
                await interaction.followup.send(note, ephemeral=True)
            except Exception:
                pass

    def _build_intro_embed(self, author) -> discord.Embed:
        mention = getattr(author, "mention", None) or "member"
        description = (
            f"Hi {mention}!\n\n"
            "Pick any filters *(you can leave some blank)* and click **Search Clans** "
            "to see Entry Criteria and open spots."
        )
        embed = discord.Embed(
            title="Search for a C1C Clan",
            description=description,
        )
        embed.set_footer(text="Only the summoner can use this panel.")
        return embed


def _close_files(files: Iterable[discord.File]) -> None:
    for file in files:
        try:
            file.close()
        except Exception:
            pass


__all__ = [
    "ACTIVE_PANELS",
    "MemberPanelControllerLegacy",
    "MemberPanelState",
]
