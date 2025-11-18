"""Embed and component helpers for the shard tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

import discord

from .mercy import MercyState, format_percent


@dataclass(frozen=True)
class ShardDisplay:
    key: str
    label: str
    owned: int
    since: int
    mercy: MercyState
    last_timestamp: str


class ShardTrackerView(discord.ui.View):
    """Interactive view exposing shard adjustment buttons."""

    def __init__(
        self,
        *,
        owner_id: int,
        controller: "ShardTrackerController",
        shard_labels: Mapping[str, str],
        disabled: bool = False,
    ) -> None:
        super().__init__(timeout=180)
        self._owner_id = owner_id
        self._controller = controller
        row_index = 0
        for key, label in shard_labels.items():
            add_button = _ShardAdjustButton(
                controller=controller,
                owner_id=owner_id,
                shard_key=key,
                action="add",
                label=f"Add {label}",
                style=discord.ButtonStyle.secondary,
                row=row_index,
                disabled=disabled,
            )
            pull_button = _ShardAdjustButton(
                controller=controller,
                owner_id=owner_id,
                shard_key=key,
                action="pull",
                label=f"Pull {label}",
                style=discord.ButtonStyle.primary,
                row=row_index,
                disabled=disabled,
            )
            self.add_item(add_button)
            self.add_item(pull_button)
            row_index += 1


class _ShardAdjustButton(discord.ui.Button[ShardTrackerView]):
    def __init__(
        self,
        *,
        controller: "ShardTrackerController",
        owner_id: int,
        shard_key: str,
        action: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._controller = controller
        self._owner_id = owner_id
        self._shard_key = shard_key
        self._action = action
        self.custom_id = f"shards:{action}:{shard_key}:{owner_id}"

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        user_id = getattr(interaction.user, "id", None)
        if user_id != self._owner_id:
            await interaction.response.send_message(
                "Only the owner of this tracker can use these buttons.",
                ephemeral=True,
            )
            return
        await self._controller.handle_button_interaction(
            interaction=interaction,
            shard_key=self._shard_key,
            action=self._action,
        )


class ShardTrackerController:
    """Protocol describing the button handler used by the view."""

    async def handle_button_interaction(
        self,
        *,
        interaction: discord.Interaction,
        shard_key: str,
        action: str,
    ) -> None:
        raise NotImplementedError


def build_summary_embed(
    *,
    member: discord.abc.User,
    displays: Sequence[ShardDisplay],
    mythic_state: MercyState,
    channel: discord.abc.GuildChannel | discord.Thread,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{member.display_name or member.name} — Shards",
        colour=discord.Color.blurple(),
    )
    total = sum(max(display.owned, 0) for display in displays)
    embed.description = (
        f"Total stash: **{total:,}** shards.\n"
        "Use the buttons below after you add or pull shards."
    )
    for display in displays:
        embed.add_field(
            name=display.label,
            value=_format_display(display),
            inline=False,
        )
    embed.add_field(
        name="Primal Mythic Mercy",
        value=_format_mythic_state(mythic_state),
        inline=False,
    )
    embed.set_footer(
        text=(
            f"Only available in #{getattr(channel, 'name', 'shards')} · "
            "Commands: !shards, !mercy, !lego, !mythic"
        )
    )
    return embed


def build_detail_embed(
    *,
    member: discord.abc.User,
    display: ShardDisplay,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{display.label} — {member.display_name or member.name}",
        colour=discord.Color.blurple(),
        description=_format_display(display),
    )
    return embed


def _format_display(display: ShardDisplay) -> str:
    parts = [
        f"Owned: **{max(display.owned, 0):,}**",
        _format_mercy_line(display.mercy),
    ]
    if display.last_timestamp:
        parts.append(f"Last LEGO: {_human_time(display.last_timestamp)}")
    return "\n".join(parts)


def _format_mercy_line(mercy: MercyState) -> str:
    chance = format_percent(mercy.current_chance)
    if mercy.profile.guarantee <= 1:
        return "Legendary chance: **100%**"
    threshold = (
        f"Starts in {mercy.pulls_until_threshold:,}"
        if mercy.pulls_until_threshold > 0
        else "Active now"
    )
    guarantee = (
        "Guaranteed on next pull"
        if mercy.pulls_until_guarantee <= 1
        else f"Pity in {mercy.pulls_until_guarantee:,}"
    )
    return f"Since LEGO: {mercy.pulls_since:,} · Chance {chance} · {threshold} · {guarantee}"


def _format_mythic_state(mercy: MercyState) -> str:
    chance = format_percent(mercy.current_chance)
    guarantee = (
        "Guaranteed on next shard"
        if mercy.pulls_until_guarantee <= 1
        else f"Guaranteed in {mercy.pulls_until_guarantee:,}"
    )
    return (
        f"Since mythic: **{mercy.pulls_since:,}** · Chance {chance} · {guarantee}"
    )


def _human_time(iso_value: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


__all__ = [
    "ShardDisplay",
    "ShardTrackerView",
    "ShardTrackerController",
    "build_summary_embed",
    "build_detail_embed",
]

