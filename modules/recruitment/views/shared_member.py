"""Legacy member results pager restored for the clan search panel."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import discord
from discord import InteractionResponded

from .. import cards, emoji_pipeline

PAGE_SIZE = 5
ALLOWED_MENTIONS = discord.AllowedMentions.none()


class MemberSearchPagedView(discord.ui.View):
    """Legacy member pager with lite/entry/profile toggles and attachments."""

    def __init__(
        self,
        *,
        author_id: int,
        rows: Sequence,
        filters_text: str,
        guild: discord.Guild | None,
        timeout: float = 900,
        mode: str = "lite",
        page: int = 0,
        empty_embed: discord.Embed | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.rows = list(rows)
        self.filters_text = filters_text
        self.guild = guild
        self.page = max(0, page)
        self.mode = mode
        self.message: discord.Message | None = None
        self.empty_embed = empty_embed
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        try:
            await interaction.response.send_message(
                "⚠️ Not your panel. Type **!clansearch** to open your own.",
                ephemeral=True,
            )
        except InteractionResponded:
            try:
                await interaction.followup.send(
                    "⚠️ Not your panel. Type **!clansearch** to open your own.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover - defensive guard
                pass
        return False

    def bind_message(self, message: discord.Message) -> None:
        self.message = message

    def _sync_state_fields(self) -> None:
        state = getattr(self, "state", None)
        updater = getattr(state, "with_updates", None)
        if callable(updater):
            try:
                self.state = updater(mode=self.mode, page=self.page)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive guard
                pass

    def _sync_buttons(self) -> None:
        max_page = max(0, math.ceil(len(self.rows) / PAGE_SIZE) - 1)
        has_rows = bool(self.rows)
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "ms_lite":
                child.disabled = not has_rows
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "lite"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_entry":
                child.disabled = not has_rows
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "entry"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_profile":
                child.disabled = not has_rows
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "profile"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_prev":
                child.disabled = not has_rows or self.page <= 0
            elif child.custom_id == "ms_next":
                child.disabled = not has_rows or self.page >= max_page

    def _make_embed(self, row) -> discord.Embed:
        if self.mode == "entry":
            return cards.make_embed_for_row_search(row, self.filters_text, self.guild)
        if self.mode == "profile":
            embed = cards.make_embed_for_profile(row, self.guild)
            if self.filters_text:
                embed.set_footer(text=f"Filters used: {self.filters_text}")
            else:
                embed.set_footer(text="")
            return embed
        embed = cards.make_embed_for_row_lite(row, self.filters_text, self.guild)
        if self.filters_text:
            embed.set_footer(text=f"Filters used: {self.filters_text}")
        return embed

    async def _build_page(self) -> tuple[list[discord.Embed], list[discord.File]]:
        if not self.rows:
            embed = self.empty_embed
            if embed is None:
                embed = discord.Embed(
                    title="No matching clans found.",
                    description="Try adjusting your filters and search again.",
                )
            return [embed], []

        start = max(0, self.page) * PAGE_SIZE
        end = min(len(self.rows), start + PAGE_SIZE)
        embeds: list[discord.Embed] = []
        files: list[discord.File] = []

        badge_size, badge_box = emoji_pipeline.tag_badge_defaults()

        for row in self.rows[start:end]:
            embed = self._make_embed(row)
            tag = ""
            try:
                tag = (row[2] or "").strip()
            except Exception:
                tag = ""
            if tag:
                file, url = await emoji_pipeline.build_tag_thumbnail(
                    self.guild, tag, size=badge_size, box=badge_box
                )
                if url and file:
                    embed.set_thumbnail(url=url)
                    files.append(file)
            embeds.append(embed)

        if embeds:
            total_pages = max(1, math.ceil(len(self.rows) / PAGE_SIZE))
            page_info = f"Page {self.page + 1}/{total_pages} • {len(self.rows)} total"
            last = embeds[-1]
            footer_text = last.footer.text or ""
            last.set_footer(
                text=f"{footer_text} • {page_info}" if footer_text else page_info
            )

        return embeds, files

    async def build_outputs(self) -> tuple[list[discord.Embed], list[discord.File]]:
        return await self._build_page()

    async def _send_refresh(
        self,
        interaction: discord.Interaction,
        *,
        embeds: Iterable[discord.Embed],
        files: Iterable[discord.File],
    ) -> None:
        embeds = list(embeds)
        files = list(files)
        try:
            sent = await interaction.followup.send(
                embeds=embeds,
                files=files,
                view=self,
                allowed_mentions=ALLOWED_MENTIONS,
            )
        finally:
            for file in files:
                try:
                    file.close()
                except Exception:
                    pass
        if self.message:
            try:
                await self.message.delete()
            except Exception:  # pragma: no cover - legacy parity
                pass
        self.message = sent

    async def _edit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except InteractionResponded:
            pass

        self._sync_state_fields()
        self._sync_buttons()
        embeds, files = await self._build_page()
        await self._send_refresh(interaction, embeds=embeds, files=files)

    @discord.ui.button(
        emoji="📇",
        label="Short view",
        style=discord.ButtonStyle.primary,
        row=0,
        custom_id="ms_lite",
    )
    async def ms_lite(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "lite"
        self.page = 0
        await self._edit(interaction)

    @discord.ui.button(
        emoji="📑",
        label="Entry Criteria",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="ms_entry",
    )
    async def ms_entry(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "entry"
        self.page = 0
        await self._edit(interaction)

    @discord.ui.button(
        emoji="🪪",
        label="Clan Profile",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="ms_profile",
    )
    async def ms_profile(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "profile"
        self.page = 0
        await self._edit(interaction)

    @discord.ui.button(
        label="◀ Prev",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="ms_prev",
    )
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.page > 0:
            self.page -= 1
        await self._edit(interaction)

    @discord.ui.button(
        label="Next ▶",
        style=discord.ButtonStyle.primary,
        row=1,
        custom_id="ms_next",
    )
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        max_page = max(0, math.ceil(len(self.rows) / PAGE_SIZE) - 1)
        if self.page < max_page:
            self.page += 1
        await self._edit(interaction)

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        row=1,
        custom_id="ms_close",
    )
    async def close(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.message:
            try:
                await self.message.delete()
                return
            except Exception:
                pass

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        embeds, _files = await self._build_page()
        if embeds:
            last = embeds[-1]
            footer_text = last.footer.text or ""
            last.set_footer(
                text=f"{footer_text} • Panel closed" if footer_text else "Panel closed"
            )
        try:
            await interaction.response.edit_message(embeds=embeds, view=self)
        except InteractionResponded:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embeds=embeds,
                view=self,
            )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:  # pragma: no cover - defensive guard
                pass

