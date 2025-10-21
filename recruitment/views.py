"""UI views for recruitment commands (no command registration in this module)."""

from __future__ import annotations

import math
from typing import Callable, Mapping, Sequence

import discord

from recruitment import cards, emoji_pipeline

PAGE_SIZE = 10


class MemberSearchPagedView(discord.ui.View):
    """Paginated member search view that cycles between lite/entry/profile layouts."""

    def __init__(
        self,
        *,
        author_id: int,
        rows: Sequence,
        filters_text: str,
        guild: discord.Guild | None,
        timeout: float = 900,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.rows = list(rows)
        self.filters_text = filters_text
        self.guild = guild
        self.page = 0
        self.mode = "lite"
        self.message: discord.Message | None = None
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        try:
            await interaction.response.send_message(
                "⚠️ Not your panel. Type **!clansearch** to open your own.",
                ephemeral=True,
            )
        except discord.InteractionResponded:
            try:
                await interaction.followup.send(
                    "⚠️ Not your panel. Type **!clansearch** to open your own.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover - defensive followup
                pass
        return False

    def _sync_buttons(self) -> None:
        max_page = max(0, math.ceil(len(self.rows) / PAGE_SIZE) - 1)
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "ms_lite":
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "lite"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_entry":
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "entry"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_profile":
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "profile"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "ms_prev":
                child.disabled = self.page <= 0
            elif child.custom_id == "ms_next":
                child.disabled = self.page >= max_page

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
        return cards.make_embed_for_row_lite(row, self.filters_text, self.guild)

    async def _build_page(self) -> tuple[list[discord.Embed], list[discord.File]]:
        start = self.page * PAGE_SIZE
        end = min(len(self.rows), start + PAGE_SIZE)
        badge_size, badge_box = emoji_pipeline.tag_badge_defaults()

        embeds: list[discord.Embed] = []
        files: list[discord.File] = []

        for row in self.rows[start:end]:
            embed = self._make_embed(row)
            tag = ""
            try:
                tag = (row[2] or "").strip()
            except Exception:
                pass
            if tag and self.guild:
                file, url = await emoji_pipeline.build_tag_thumbnail(
                    self.guild,
                    tag,
                    size=badge_size,
                    box=badge_box,
                )
                if file and url:
                    embed.set_thumbnail(url=url)
                    files.append(file)
            embeds.append(embed)

        if embeds:
            total_pages = max(1, math.ceil(len(self.rows) / PAGE_SIZE))
            page_info = f"Page {self.page + 1}/{total_pages} • {len(self.rows)} total"
            last = embeds[-1]
            existing_footer = last.footer.text or ""
            last.set_footer(
                text=f"{existing_footer} • {page_info}" if existing_footer else page_info
            )

        return embeds, files

    async def _edit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        self._sync_buttons()
        embeds, files = await self._build_page()

        sent = await interaction.followup.send(embeds=embeds, files=files, view=self)

        if self.message is not None:
            try:
                await self.message.delete()
            except Exception:  # pragma: no cover - cleanup best effort
                pass
        self.message = sent

    @discord.ui.button(
        emoji="📇",
        label="Short view",
        style=discord.ButtonStyle.primary,
        row=0,
        custom_id="ms_lite",
    )
    async def ms_lite(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "lite"
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
        try:
            await interaction.message.delete()
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
        except discord.InteractionResponded:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embeds=embeds,
                view=self,
            )

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is None:
            return
        try:
            embeds, _files = await self._build_page()
            if embeds:
                last = embeds[-1]
                footer_text = last.footer.text or ""
                last.set_footer(
                    text=f"{footer_text} • Expired" if footer_text else "Expired"
                )
            await self.message.edit(embeds=embeds, view=self)
        except Exception:  # pragma: no cover - cleanup best effort
            pass


class SearchResultFlipView(discord.ui.View):
    """Single-result view that flips between lite/profile/entry embeds."""

    def __init__(
        self,
        *,
        author_id: int,
        row,
        filters_text: str,
        guild: discord.Guild | None,
        timeout: float = 900,
        default_mode: str = "lite",
        embed_builders: Mapping[str, Callable[[], discord.Embed]] | None = None,
        not_owner_message: str | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.row = row
        self.filters_text = filters_text
        self.guild = guild
        self.mode = default_mode
        self.message: discord.Message | None = None
        self._builders = dict(embed_builders or {})
        self._not_owner_message = (
            not_owner_message
            or "⚠️ Not your result. Open your own with **!clansearch**."
        )
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        try:
            await interaction.response.send_message(
                self._not_owner_message,
                ephemeral=True,
            )
        except discord.InteractionResponded:
            try:
                await interaction.followup.send(
                    self._not_owner_message,
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover - defensive followup
                pass
        return False

    def _sync_buttons(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "sr_profile":
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "profile"
                    else discord.ButtonStyle.secondary
                )
            elif child.custom_id == "sr_entry":
                child.style = (
                    discord.ButtonStyle.primary
                    if self.mode == "entry"
                    else discord.ButtonStyle.secondary
                )

    def _build_embed(self) -> discord.Embed:
        builder = self._builders.get(self.mode)
        if builder is not None:
            return builder()
        if self.mode == "profile":
            embed = cards.make_embed_for_profile(self.row, self.guild)
            if self.filters_text:
                embed.set_footer(text=f"Filters used: {self.filters_text}")
            else:
                embed.set_footer(text="")
            return embed
        if self.mode == "entry":
            return cards.make_embed_for_row_search(self.row, self.filters_text, self.guild)
        return cards.make_embed_for_row_lite(self.row, self.filters_text, self.guild)

    async def _edit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        self._sync_buttons()
        embed = self._build_embed()

        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                view=self,
            )

    @discord.ui.button(
        emoji="👤",
        label="See clan profile",
        style=discord.ButtonStyle.secondary,
        custom_id="sr_profile",
    )
    async def profile_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "profile"
        await self._edit(interaction)

    @discord.ui.button(
        emoji="✅",
        label="See entry criteria",
        style=discord.ButtonStyle.secondary,
        custom_id="sr_entry",
    )
    async def entry_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.mode = "entry"
        await self._edit(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:  # pragma: no cover - cleanup best effort
            pass
