"""Embed and component helpers for the shard tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

import discord

from shared import theme

from .mercy import MercySnapshot, format_percent


TAB_LABELS: Mapping[str, str] = {
    "overview": "Overview",
    "ancient": "Ancient",
    "void": "Void",
    "sacred": "Sacred",
    "primal": "Primal",
    "last_pulls": "Last Pulls",
}


@dataclass(frozen=True)
class ShardDisplay:
    key: str
    label: str
    owned: int
    mercy: MercySnapshot
    last_timestamp: str
    last_depth: int


@dataclass(frozen=True)
class MythicDisplay:
    mercy: MercySnapshot
    last_timestamp: str
    last_depth: int


class ShardTrackerView(discord.ui.View):
    """Interactive view for the tabbed shard tracker."""

    def __init__(
        self,
        *,
        owner_id: int,
        controller: "ShardTrackerController",
        active_tab: str,
        shard_labels: Mapping[str, str],
        shard_emojis: Mapping[str, discord.PartialEmoji | None],
        mythic_controls: bool = True,
        timeout: float | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.active_tab = active_tab
        self._controller = controller
        # Tab buttons
        for tab in ("overview", "ancient", "void", "sacred", "primal", "last_pulls"):
            label: str | None = None
            emoji = None

            if tab in ("overview", "last_pulls"):
                label = TAB_LABELS[tab]
            else:
                emoji = shard_emojis.get(tab)
                if not emoji or not getattr(emoji, "id", None):
                    emoji = None
                    label = TAB_LABELS[tab]
            style = discord.ButtonStyle.primary if tab == active_tab else discord.ButtonStyle.secondary
            self.add_item(
                _ShardButton(
                    custom_id=f"tab:{tab}",
                    label=label,
                    emoji=emoji,
                    style=style,
                    owner_id=owner_id,
                    controller=controller,
                )
            )

        # Action rows depend on tab
        if active_tab in shard_labels:
            self._add_primary_buttons()
            self._add_legendary_button()
            self._add_last_pulls_button()

    def _add_primary_buttons(self) -> None:
        self.add_item(
            _ShardButton(
                custom_id=f"action:stash:{self.active_tab}",
                label="+ Stash",
                emoji=None,
                style=discord.ButtonStyle.primary,
                owner_id=self.owner_id,
                controller=self._controller,
            )
        )
        self.add_item(
            _ShardButton(
                custom_id=f"action:pulls:{self.active_tab}",
                label="- Pulls",
                emoji=None,
                style=discord.ButtonStyle.secondary,
                owner_id=self.owner_id,
                controller=self._controller,
            )
        )

    def _add_legendary_button(self) -> None:
        label = "Got Legendary/Mythical" if self.active_tab == "primal" else "Got Legendary"
        self.add_item(
            _ShardButton(
                custom_id=f"action:legendary:{self.active_tab}",
                label=label,
                emoji=None,
                style=discord.ButtonStyle.success,
                owner_id=self.owner_id,
                controller=self._controller,
            )
        )

    def _add_last_pulls_button(self) -> None:
        self.add_item(
            _ShardButton(
                custom_id=f"action:last_pulls:{self.active_tab}",
                label="Last Pulls / Mercy",
                emoji=None,
                style=discord.ButtonStyle.secondary,
                owner_id=self.owner_id,
                controller=self._controller,
            )
        )


class _ShardButton(discord.ui.Button[ShardTrackerView]):
    def __init__(
        self,
        *,
        custom_id: str,
        label: str,
        emoji: discord.PartialEmoji | None,
        style: discord.ButtonStyle,
        owner_id: int,
        controller: "ShardTrackerController",
        ) -> None:
        super().__init__(custom_id=custom_id, label=label, style=style, emoji=emoji)
        self._owner_id = owner_id
        self._controller = controller

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        user_id = getattr(interaction.user, "id", None)
        owner_id = self._owner_id
        if owner_id and user_id != owner_id:
            await interaction.response.send_message(
                "Only the owner of this tracker can use these buttons.", ephemeral=True
            )
            return
        await self._controller.handle_button_interaction(
            interaction=interaction,
            custom_id=self.custom_id,
            active_tab=self.custom_id.split(":")[-1]
            if self.custom_id.startswith("action:") or self.custom_id.startswith("tab:")
            else self.view.active_tab if isinstance(self.view, ShardTrackerView) else "overview",
        )


_TAB_COLORS: Mapping[str, discord.Colour] = {
    "overview": theme.colors.c1c_blue,
    "last_pulls": theme.colors.c1c_blue,
    "ancient": discord.Colour(0x5CC8FF),
    "void": discord.Colour(0xA970FF),
    "sacred": discord.Colour.gold(),
    "primal": discord.Colour.dark_red(),
}


_AUTHOR_NAMES: Mapping[str, str] = {
    "overview": "Shard Overview — C1C",
    "last_pulls": "Last Pulls & Mercy Info — C1C",
    "ancient": "Ancient Shards",
    "void": "Void Shards",
    "sacred": "Sacred Shards",
    "primal": "Primal Shards",
}


class ShardTrackerController:
    async def handle_button_interaction(
        self,
        *,
        interaction: discord.Interaction,
        custom_id: str,
        active_tab: str,
    ) -> None:
        raise NotImplementedError


def build_overview_embed(
    *,
    member: discord.abc.User,
    displays: Sequence[ShardDisplay],
    mythic: MythicDisplay,
    author_name: str | None = None,
    author_icon_url: str | None = None,
    color: discord.Colour | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        colour=color or _TAB_COLORS.get("overview"),
        description=(
            "Snapshot across all shard types. Use the tab buttons for details "
            "and the Legendary/Mythical buttons to log pulls."
        ),
    )
    embed.set_author(
        name=author_name or _AUTHOR_NAMES.get("overview"),
        icon_url=author_icon_url,
    )
    for display in displays:
        line = (
            f"Owned: **{max(display.owned, 0):,}** | "
            f"Mercy: {display.mercy.pulls_since} / {display.mercy.threshold} | "
            f"Chance: {format_percent(display.mercy.chance)}"
        )
        if display.last_timestamp:
            line += f"\nLast Legendary: {human_time(display.last_timestamp)}"
        embed.add_field(name=display.label, value=line, inline=False)

    mythic_line = (
        f"Mercy: {mythic.mercy.pulls_since} / {mythic.mercy.threshold} | "
        f"Chance: {format_percent(mythic.mercy.chance)}"
    )
    if mythic.last_timestamp:
        mythic_line += f"\nLast Mythical: {human_time(mythic.last_timestamp)}"
    embed.add_field(name="Primal (Mythical)", value=mythic_line, inline=False)
    return embed


def build_detail_embed(
    *,
    member: discord.abc.User,
    display: ShardDisplay,
    mythic: MythicDisplay | None = None,
    author_name: str | None = None,
    author_icon_url: str | None = None,
    color: discord.Colour | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        colour=color or _TAB_COLORS.get(display.key, _TAB_COLORS["overview"])
    )
    embed.set_author(
        name=author_name or _AUTHOR_NAMES.get(display.key, display.label),
        icon_url=author_icon_url,
    )
    embed.description = _detail_block(display)
    embed.add_field(
        name="Progress",
        value=_progress_bar(display.mercy),
        inline=False,
    )
    if mythic:
        embed.add_field(name="Primal Mythical", value=_mythic_block(mythic), inline=False)
    return embed


def build_last_pulls_embed(
    *,
    member: discord.abc.User,
    displays: Sequence[ShardDisplay],
    mythic: MythicDisplay,
    base_rates: Mapping[str, str],
    author_name: str | None = None,
    author_icon_url: str | None = None,
    color: discord.Colour | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        colour=color or _TAB_COLORS.get("last_pulls", _TAB_COLORS["overview"])
    )
    embed.set_author(
        name=author_name or _AUTHOR_NAMES.get("last_pulls"),
        icon_url=author_icon_url,
    )
    last_lines = []
    for display in displays:
        stamp = human_time(display.last_timestamp) if display.last_timestamp else "Never"
        depth = f" ({display.last_depth} at pull)" if display.last_depth > 0 else ""
        last_lines.append(f"{display.label} Legendary: {stamp}{depth}")
    mythic_stamp = human_time(mythic.last_timestamp) if mythic.last_timestamp else "Never"
    mythic_depth = f" ({mythic.last_depth} at pull)" if mythic.last_depth > 0 else ""
    last_lines.append(f"Primal Mythical: {mythic_stamp}{mythic_depth}")
    embed.add_field(name="Last Pulls", value="\n".join(last_lines), inline=False)

    info_lines = [
        "**Mercy System (official rates)**",
        "Ancient/Void Legendary: after 200 pulls, +5% per shard",
        "Sacred Legendary: after 12 pulls, +2% per shard",
        "Primal Legendary: after 75 pulls, +1% per shard",
        "Primal Mythical: after 200 pulls, +10% per shard",
        "\nBase chances:",
        "```",
    ]
    for label, rate in base_rates.items():
        info_lines.append(f"{label:<18} {rate}")
    info_lines.append("```")
    embed.add_field(name="Mercy Info", value="\n".join(info_lines), inline=False)
    return embed


def _detail_block(display: ShardDisplay) -> str:
    mercy = display.mercy
    maxed = mercy.pulls_since >= mercy.threshold
    parts = [
        f"Stash: **{max(display.owned, 0):,}**",
    ]
    if display.key == "primal":
        parts.append("")
        parts.append("**Primal Legendary**")
    parts.extend(
        [
            f"Legendary Mercy: {mercy.pulls_since} / {mercy.threshold}" + (" (Maxed)" if maxed else ""),
            f"Legendary Chance: {format_percent(mercy.chance)}",
        ]
    )
    if display.last_timestamp:
        parts.append(
            f"Last Legendary: {human_time(display.last_timestamp)}"
            + (f" ({display.last_depth} depth)" if display.last_depth else "")
        )
    return "\n".join(parts)


def _mythic_block(display: MythicDisplay) -> str:
    mercy = display.mercy
    maxed = mercy.pulls_since >= mercy.threshold
    parts = [
        f"Mythical Mercy: {mercy.pulls_since} / {mercy.threshold}" + (" (Maxed)" if maxed else ""),
        f"Mythical Chance: {format_percent(mercy.chance)}",
    ]
    if display.last_timestamp:
        parts.append(
            f"Last Mythical: {human_time(display.last_timestamp)}"
            + (f" ({display.last_depth} depth)" if display.last_depth else "")
        )
    parts.extend(["", "Progress", _progress_bar(mercy)])
    return "\n".join(parts)


def _progress_bar(mercy: MercySnapshot, segments: int = 10) -> str:
    max_pulls = max(mercy.cap_at, mercy.threshold)
    capped = min(mercy.pulls_since, max_pulls)
    filled = int(round((capped / max_pulls) * segments)) if max_pulls else 0
    threshold_segments = int(round((mercy.threshold / max_pulls) * segments)) if max_pulls else 0
    base_filled = min(filled, threshold_segments)
    mercy_filled = max(0, filled - threshold_segments)
    empty = max(0, segments - filled)
    bar = "".join([
        "🟩" * base_filled,
        "🟦" * mercy_filled,
        "⬜" * empty,
    ])
    return bar


def human_time(iso_value: str) -> str:
    if not iso_value:
        return ""
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


__all__ = [
    "ShardDisplay",
    "MythicDisplay",
    "ShardTrackerView",
    "ShardTrackerController",
    "build_overview_embed",
    "build_detail_embed",
    "build_last_pulls_embed",
    "human_time",
]
