"""Member-facing clan search controller and helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import discord
from discord import Message
from discord.ext import commands

from .. import search_helpers
from ..search_helpers import (
    format_filters_footer,
    parse_inactives_num,
    parse_spots_num,
    row_matches,
)
from .shared import MemberSearchPagedView
from shared import config as shared_config
from shared.sheets.async_facade import fetch_clans_async

log = logging.getLogger(__name__)

MAX_VISIBLE_ROWS = 5


@dataclass
class MemberSearchFilters:
    """Snapshot of all clan-search filters selected by the member."""

    cb: str | None = None
    hydra: str | None = None
    chimera: str | None = None
    cvc: str | None = None
    siege: str | None = None
    playstyle: str | None = None
    roster_mode: str | None = "open"

    def any_active(self) -> bool:
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

    def copy(self) -> "MemberSearchFilters":
        return MemberSearchFilters(
            cb=self.cb,
            hydra=self.hydra,
            chimera=self.chimera,
            cvc=self.cvc,
            siege=self.siege,
            playstyle=self.playstyle,
            roster_mode=self.roster_mode,
        )


# Track the active results message per (guild_id, channel_id, user_id)
ACTIVE_PANELS: dict[tuple[int, int, int], int] = {}


def _coerce_filters(raw: MemberSearchFilters | Mapping[str, object]) -> MemberSearchFilters:
    if isinstance(raw, MemberSearchFilters):
        return raw

    data = dict(raw)
    return MemberSearchFilters(
        cb=data.get("cb") or None,
        hydra=data.get("hydra") or None,
        chimera=data.get("chimera") or None,
        cvc=data.get("cvc") or None,
        siege=data.get("siege") or None,
        playstyle=data.get("playstyle") or None,
        roster_mode=data.get("roster_mode") or None,
    )


class MemberPanelController:
    """Manage the lifecycle of member search results in a single message."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def open_or_reuse(self, ctx: commands.Context) -> None:
        """Ensure a results message exists for ``ctx.author`` in this channel."""

        filters = MemberSearchFilters()
        await self.update_results(ctx, filters=filters)

    async def update_results(
        self,
        ctx: commands.Context | None,
        *,
        filters: MemberSearchFilters | Mapping[str, object],
        interaction: discord.Interaction | None = None,
    ) -> None:
        """Rebuild the member search results based on ``filters``.

        ``ctx`` may be ``None`` when invoked from an interaction callback; in that
        case an ``interaction`` must be provided.
        """

        if ctx is None and interaction is None:
            raise ValueError("either ctx or interaction must be provided")

        filters = _coerce_filters(filters).copy()

        channel = None
        guild = None
        author_id: int | None = None

        if ctx is not None:
            channel = getattr(ctx, "channel", None)
            guild = getattr(ctx, "guild", None)
            author = getattr(ctx, "author", None)
            if author is not None:
                author_id = getattr(author, "id", None)

        if interaction is not None:
            if interaction.channel is not None:
                channel = interaction.channel
            if interaction.guild is not None:
                guild = interaction.guild
            if interaction.user is not None:
                author_id = getattr(interaction.user, "id", author_id)

        if channel is None or author_id is None:
            return

        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return

        guild_id = getattr(guild, "id", 0) or 0
        key = (int(guild_id), int(channel_id), int(author_id))

        message = await self._fetch_existing_message(channel, key)

        rows = await self._load_rows()
        matches = self._filter_rows(rows, filters)

        soft_cap = max(1, shared_config.get_search_results_soft_cap(25))
        visible_cap = min(soft_cap, MAX_VISIBLE_ROWS)
        total_found = len(matches)
        visible_rows = matches[:visible_cap]

        cap_note = None
        if total_found > visible_cap:
            cap_note = f"first {visible_cap} of {total_found}"

        filters_text = format_filters_footer(
            filters.cb,
            filters.hydra,
            filters.chimera,
            filters.cvc,
            filters.siege,
            filters.playstyle,
            filters.roster_mode,
            extra_note=cap_note,
        )

        if not visible_rows:
            embed = discord.Embed(
                title="No matching clans found.",
                description="Try adjusting your filters and search again.",
            )
            if filters_text:
                embed.set_footer(text=f"Filters used: {filters_text}")
            await self._send_or_edit(
                channel,
                key,
                message,
                content=None,
                embeds=[embed],
                files=[],
                view=None,
                interaction=interaction,
                ctx=ctx,
            )
            return

        view = MemberSearchPagedView(
            author_id=int(author_id),
            rows=visible_rows,
            filters_text=filters_text,
            guild=guild,
        )
        embeds, files = await view.build_outputs()

        await self._send_or_edit(
            channel,
            key,
            message,
            content=None,
            embeds=embeds,
            files=files,
            view=view,
            interaction=interaction,
            ctx=ctx,
        )

    async def _fetch_existing_message(
        self,
        channel,
        key: tuple[int, int, int],
    ) -> Message | None:
        message_id = ACTIVE_PANELS.get(key)
        if not message_id:
            return None

        fetcher = getattr(channel, "fetch_message", None)
        if fetcher is None:
            ACTIVE_PANELS.pop(key, None)
            return None

        try:
            message = await fetcher(message_id)
        except discord.NotFound:
            ACTIVE_PANELS.pop(key, None)
            return None
        except discord.Forbidden:
            ACTIVE_PANELS.pop(key, None)
            log.warning(
                "member clansearch cannot fetch message due to permissions", extra={"key": key}
            )
            return None
        except discord.HTTPException:
            log.exception("member clansearch failed to fetch message", extra={"key": key})
            return None

        return message

    async def _send_or_edit(
        self,
        channel,
        key: tuple[int, int, int],
        existing: Message | None,
        *,
        content: str | None,
        embeds: Sequence[discord.Embed],
        files: Iterable[discord.File],
        view: discord.ui.View | None,
        interaction: discord.Interaction | None,
        ctx: commands.Context | None,
    ) -> None:
        attachments = list(files)

        if existing is None:
            if interaction is not None and not interaction.response.is_done():
                send = interaction.response.send_message
            elif interaction is not None:
                send = interaction.followup.send
            else:
                send = None
                if ctx is not None:
                    reply_fn = getattr(ctx, "reply", None)
                    if reply_fn is not None:
                        async def _reply_wrapper(*args, **kwargs):
                            kwargs.setdefault("mention_author", False)
                            return await reply_fn(*args, **kwargs)

                        send = _reply_wrapper
                if send is None:
                    send = getattr(channel, "send", None)
            if send is None:
                return
            sent = await send(content=content, embeds=list(embeds), files=attachments, view=view)
            if hasattr(sent, "id"):
                ACTIVE_PANELS[key] = getattr(sent, "id")
                if isinstance(view, MemberSearchPagedView):
                    view.message = sent  # type: ignore[assignment]
            return

        try:
            await existing.edit(
                content=content,
                embeds=list(embeds),
                attachments=attachments,
                view=view,
            )
        except discord.HTTPException:
            log.exception("member clansearch failed to edit results message", extra={"key": key})
            return
        else:
            ACTIVE_PANELS[key] = existing.id
            if isinstance(view, MemberSearchPagedView):
                view.message = existing

    async def _load_rows(self) -> list[Sequence[str]]:
        try:
            rows = await fetch_clans_async(force=False)
        except Exception:  # pragma: no cover - defensive guard
            log.exception("failed to fetch member clan rows")
            return []
        return rows or []

    def _filter_rows(
        self, rows: Sequence[Sequence[str]], filters: MemberSearchFilters
    ) -> list[Sequence[str]]:
        matches: list[Sequence[str]] = []
        if not rows:
            return matches

        for row in rows[1:]:
            try:
                if not row_matches(
                    row,
                    filters.cb,
                    filters.hydra,
                    filters.chimera,
                    filters.cvc,
                    filters.siege,
                    filters.playstyle,
                ):
                    continue
                spots = parse_spots_num(
                    row[search_helpers.COL_E_SPOTS]
                    if len(row) > search_helpers.COL_E_SPOTS
                    else ""
                )
                inactives = parse_inactives_num(
                    row[search_helpers.IDX_AF_INACTIVES]
                    if len(row) > search_helpers.IDX_AF_INACTIVES
                    else ""
                )
                if filters.roster_mode == "open" and spots <= 0:
                    continue
                if filters.roster_mode == "full" and spots > 0:
                    continue
                if filters.roster_mode == "inactives" and inactives <= 0:
                    continue
                matches.append(row)
            except Exception:
                continue

        return matches

