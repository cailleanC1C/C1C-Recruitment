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
from .filters_member import MemberFiltersRow
from .shared_member import MemberSearchPagedView
from shared import config as shared_config
from shared.sheets.async_facade import fetch_clans_async

log = logging.getLogger("c1c.recruitment.member.legacy")

ALLOWED_MENTIONS = discord.AllowedMentions.none()


def _build_empty_embed(filters_text: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="No matching clans found.",
        description="Try adjusting your filters and search again.",
    )
    if filters_text:
        embed.set_footer(text=f"Filters used: {filters_text}")
    return embed


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
    mode: str = "lite"
    page: int = 0

    def copy(self) -> "MemberPanelState":
        return replace(self)

    def with_updates(self, **changes) -> "MemberPanelState":
        return replace(self, **changes)


class MemberPanelLegacyView(MemberFiltersRow, MemberSearchPagedView):
    """Composite view combining legacy filters with the results pager."""

    def __init__(
        self,
        *,
        controller: "MemberPanelControllerLegacy",
        state: MemberPanelState,
        rows: Sequence,
        filters_text: str,
        guild: discord.Guild | None,
        empty_embed: discord.Embed | None,
    ) -> None:
        self.state = state.copy()
        self.controller = controller
        MemberSearchPagedView.__init__(
            self,
            author_id=state.author_id,
            rows=rows,
            filters_text=filters_text,
            guild=guild,
            timeout=900,
            mode=state.mode,
            page=state.page,
            empty_embed=empty_embed,
        )
        MemberFiltersRow.__init__(self, controller=controller, state=self.state)
        self._sync_buttons()
        self._sync_filter_labels()

    async def build_outputs(self) -> tuple[list[discord.Embed], list[discord.File]]:
        return await MemberSearchPagedView.build_outputs(self)


class MemberPanelControllerLegacy:
    """Restore the legacy new-message-per-change member clan search."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def open(self, ctx: commands.Context) -> None:
        channel = getattr(ctx, "channel", None)
        if channel is None:
            return

        author = getattr(ctx, "author", None)
        if author is None:
            return

        state = MemberPanelState(author_id=getattr(author, "id"))

        await self._send_panel(
            state=state,
            channel=channel,
            guild=getattr(ctx, "guild", None),
            ctx=ctx,
        )

    async def refresh_from_filters(
        self, interaction: discord.Interaction, state: MemberPanelState
    ) -> None:
        try:
            await self._send_panel(state=state, interaction=interaction)
        except Exception as exc:  # pragma: no cover - defensive guard
            log.exception("member panel filter refresh failed", exc_info=exc)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Sorry — I couldn't refresh those results.",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        "❌ Sorry — I couldn't refresh those results.",
                        ephemeral=True,
                    )
            except Exception:
                pass

    async def _send_panel(
        self,
        *,
        state: MemberPanelState,
        channel: discord.abc.Messageable | None = None,
        guild: discord.Guild | None = None,
        ctx: commands.Context | None = None,
        interaction: discord.Interaction | None = None,
    ) -> None:
        if interaction is not None:
            if channel is None:
                channel = interaction.channel
            if guild is None:
                guild = interaction.guild

        if channel is None:
            return

        rows = await self._load_rows()
        matches = self._filter_rows(rows, state)

        total_found = len(matches)
        cap = max(1, shared_config.get_search_results_soft_cap(25))
        cap_note = None
        if total_found > cap:
            matches = matches[:cap]
            cap_note = f"first {cap} of {total_found}"

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

        empty_embed = _build_empty_embed(filters_text)

        view = MemberPanelLegacyView(
            controller=self,
            state=state,
            rows=matches,
            filters_text=filters_text,
            guild=guild,
            empty_embed=empty_embed,
        )

        embeds, files = await view.build_outputs()
        if not embeds:
            embeds = [empty_embed]

        send_kwargs = {
            "embeds": embeds,
            "files": files,
            "view": view,
            "allowed_mentions": ALLOWED_MENTIONS,
        }

        try:
            if interaction is not None:
                if not interaction.response.is_done():
                    try:
                        await interaction.response.defer()
                    except InteractionResponded:
                        pass
                sent = await interaction.followup.send(**send_kwargs)
            else:
                send = getattr(channel, "send", None)
                if send is None:
                    return
                sent = await send(**send_kwargs)
        except discord.Forbidden as exc:
            log.warning("member panel send forbidden", exc_info=exc)
            return
        except discord.HTTPException as exc:
            log.exception("member panel send failed", exc_info=exc)
            return
        finally:
            _close_files(files)

        if isinstance(sent, discord.Message):
            view.bind_message(sent)

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


def _close_files(files: Iterable[discord.File]) -> None:
    for file in files:
        try:
            file.close()
        except Exception:
            pass


__all__ = [
    "MemberPanelControllerLegacy",
    "MemberPanelState",
]

