"""Embed and component helpers for the shard tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

import discord

from .mercy import MercySnapshot, format_percent


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
        mythic_controls: bool = True,
    ) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.active_tab = active_tab
        self._controller = controller
        # Tab buttons
        for tab in ("overview", "ancient", "void", "sacred", "primal", "last_pulls"):
            label = tab.replace("_", " ").title()
            style = discord.ButtonStyle.primary if tab == active_tab else discord.ButtonStyle.secondary
            self.add_item(
                _ShardButton(
                    custom_id=f"tab:{tab}",
                    label=label,
                    style=style,
                    owner_id=owner_id,
                    controller=controller,
                )
            )

        # Action rows depend on tab
        if active_tab in shard_labels:
            self._add_stash_buttons(active_tab)
            self._add_legendary_button(active_tab, shard_labels[active_tab])
            if active_tab == "primal" and mythic_controls:
                self._add_primal_mythic_buttons()

    def _add_stash_buttons(self, shard_key: str) -> None:
        for delta in (-10, -5, -1, 1, 5, 10):
            label = f"{delta:+d}"
            self.add_item(
                _ShardButton(
                    custom_id=f"{shard_key}:add:{delta}",
                    label=label,
                    style=discord.ButtonStyle.secondary,
                    owner_id=self.owner_id,
                    controller=self._controller,
                )
            )

    def _add_legendary_button(self, shard_key: str, label: str) -> None:
        self.add_item(
            _ShardButton(
                custom_id=f"{shard_key}:got_legendary",
                label=f"Got Legendary ({label})",
                style=discord.ButtonStyle.success,
                owner_id=self.owner_id,
                controller=self._controller,
            )
        )

    def _add_primal_mythic_buttons(self) -> None:
        for delta in (-5, -1, 1, 5):
            self.add_item(
                _ShardButton(
                    custom_id=f"primal_mythic:add:{delta}",
                    label=f"Mythic {delta:+d}",
                    style=discord.ButtonStyle.secondary,
                    owner_id=self.owner_id,
                    controller=self._controller,
                )
            )
        self.add_item(
            _ShardButton(
                custom_id="primal:got_mythical",
                label="Got Mythical",
                style=discord.ButtonStyle.success,
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
        style: discord.ButtonStyle,
        owner_id: int,
        controller: "ShardTrackerController",
    ) -> None:
        super().__init__(custom_id=custom_id, label=label, style=style)
        self._owner_id = owner_id
        self._controller = controller

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        user_id = getattr(interaction.user, "id", None)
        if user_id != self._owner_id:
            await interaction.response.send_message(
                "Only the owner of this tracker can use these buttons.", ephemeral=True
            )
            return
        await self._controller.handle_button_interaction(
            interaction=interaction,
            custom_id=self.custom_id,
            active_tab=self.view.active_tab if isinstance(self.view, ShardTrackerView) else "overview",
        )


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
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Shard Overview — {member.display_name or member.name}",
        colour=discord.Color.blurple(),
        description=(
            "Snapshot across all shard types. Use the tab buttons for details "
            "and the Legendary/Mythical buttons to log pulls."
        ),
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
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{display.label} Shards", colour=discord.Color.blurple()
    )
    embed.description = _detail_block(display)
    if mythic:
        embed.add_field(name="Primal Mythical", value=_mythic_block(mythic), inline=False)
    return embed


def build_last_pulls_embed(
    *,
    member: discord.abc.User,
    displays: Sequence[ShardDisplay],
    mythic: MythicDisplay,
    base_rates: Mapping[str, str],
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Last Pulls & Mercy Info — {member.display_name or member.name}",
        colour=discord.Color.blurple(),
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
    remaining = max(0, mercy.threshold - mercy.pulls_since)
    remaining_label = f"{remaining} left" if remaining > 0 else "Maxed"
    parts = [
        f"Stash: **{max(display.owned, 0):,}**",
        f"Legendary Mercy: {mercy.pulls_since} / {mercy.threshold} ({remaining_label})",
        f"Legendary Chance: {format_percent(mercy.chance)}",
        _progress_bar(mercy),
    ]
    if display.last_timestamp:
        parts.append(
            f"Last Legendary: {human_time(display.last_timestamp)}"
            + (f" ({display.last_depth} depth)" if display.last_depth else "")
        )
    return "\n".join(parts)


def _mythic_block(display: MythicDisplay) -> str:
    mercy = display.mercy
    remaining = max(0, mercy.threshold - mercy.pulls_since)
    remaining_label = f"{remaining} left" if remaining > 0 else "Maxed"
    parts = [
        f"Mythical Mercy: {mercy.pulls_since} / {mercy.threshold} ({remaining_label})",
        f"Mythical Chance: {format_percent(mercy.chance)}",
        _progress_bar(mercy),
    ]
    if display.last_timestamp:
        parts.append(
            f"Last Mythical: {human_time(display.last_timestamp)}"
            + (f" ({display.last_depth} depth)" if display.last_depth else "")
        )
    return "\n".join(parts)


def _progress_bar(mercy: MercySnapshot, segments: int = 20) -> str:
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
    return f"Progress: [{bar}] {mercy.pulls_since}/{max_pulls}"


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
