"""CoreOps help metadata and embed builders."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import discord

COREOPS_VERSION = "1.5.0"


@dataclass(frozen=True)
class HelpCommandInfo:
    """Immutable description of a command for help rendering."""

    qualified_name: str
    signature: str
    short: str
    detailed: str
    aliases: Sequence[str]
    access_tier: str
    function_group: str
    section: str | None = None
    usage_override: str | None = None
    flags: Sequence[str] = ()




@dataclass(frozen=True)
class HelpOverviewSection:
    """Collection of commands rendered together in the overview help embed."""

    label: str
    blurb: str
    commands: Sequence[HelpCommandInfo]


@dataclass(frozen=True)
class HelpTierSection:
    """Section rendered inside a tier-specific help embed."""

    label: str
    commands: Sequence[HelpCommandInfo]


@dataclass(frozen=True)
class HelpTier:
    """Tier-specific help embed metadata."""

    title: str
    sections: Sequence[HelpTierSection]


def build_coreops_footer(
    *, bot_version: str, coreops_version: str = COREOPS_VERSION, notes: str | None = None
) -> str:
    footer = f"Bot v{bot_version} · CoreOps v{coreops_version}"
    if notes:
        trimmed = notes.strip()
        if trimmed:
            # Preserve the caller's chosen separator (bullet, middot, etc.).
            footer = f"{footer}{notes}"
    return footer


def build_help_footer(*, bot_version: str) -> str:
    """Backward-compatible alias for callers expecting the legacy name."""

    return build_coreops_footer(bot_version=bot_version)


def build_help_overview_embed(
    *,
    prefix: str,
    sections: Sequence[HelpOverviewSection],
    bot_version: str,
    bot_name: str,
    bot_description: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{bot_name} · help",
        colour=discord.Color.blurple(),
    )

    embed.description = bot_description.strip()

    for section in sections:
        commands = [command for command in section.commands if command]
        if not commands:
            continue
        lines = [_format_summary_line(prefix, command) for command in commands]
        value = _format_section_value(section.blurb, lines)
        embed.add_field(name=section.label, value=value, inline=False)

    footer_text = build_coreops_footer(bot_version=bot_version)
    embed.set_footer(text=footer_text)
    return embed


def build_help_detail_embed(
    *,
    prefix: str,
    command: HelpCommandInfo,
    bot_version: str,
    bot_name: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=_format_usage(prefix, command.qualified_name, None),
        colour=discord.Color.blurple(),
        description=command.detailed.strip() if command.detailed else "—",
    )

    usage_text = _format_usage(prefix, command.qualified_name, command.signature)
    embed.add_field(name="Usage", value=usage_text, inline=False)

    if command.aliases:
        alias_values = [
            f"`{_format_usage(prefix, alias.strip(), None)}`"
            for alias in command.aliases
            if alias and alias.strip()
        ]
        if alias_values:
            embed.add_field(
                name="Aliases",
                value=", ".join(alias_values),
                inline=False,
            )

    footer_text = build_coreops_footer(bot_version=bot_version)
    embed.set_footer(text=footer_text)
    return embed


def build_help_overview_embeds(
    *,
    prefix: str,
    overview_title: str,
    overview_description: str,
    tiers: Sequence[HelpTier],
    bot_version: str,
    notes: str = "",
    colour: discord.Colour | None = None,
    show_empty_sections: bool = False,
) -> list[discord.Embed]:
    """Return the ordered embed list for the multi-pane overview."""

    embeds: list[discord.Embed] = []
    colour = colour or discord.Color.blurple()
    footer_text = build_coreops_footer(bot_version=bot_version, notes=notes)

    overview = discord.Embed(title=overview_title, colour=colour)
    overview.description = overview_description.strip()
    overview.set_footer(text=footer_text)
    embeds.append(overview)

    for tier in tiers:
        embed = discord.Embed(title=tier.title, colour=colour)
        field_total = 0
        for section in tier.sections:
            chunks = _build_section_chunks(
                prefix,
                section.label,
                section.commands,
                show_empty=show_empty_sections,
            )
            for name, value in chunks:
                embed.add_field(name=name, value=value, inline=False)
                field_total += 1
                if field_total >= 12:
                    break
            if field_total >= 12:
                break
        embed.set_footer(text=footer_text)
        embeds.append(embed)

    return embeds


def _format_usage(prefix: str, qualified_name: str, signature: str | None) -> str:
    sig = (signature or "").strip()
    name = (qualified_name or "").strip()
    prefix_text = prefix or ""
    return f"{prefix_text}{name}{(' ' + sig) if sig else ''}"


def _format_summary_line(prefix: str, command: HelpCommandInfo) -> str:
    return _format_overview_lines(prefix, command)[0]


def _format_section_value(blurb: str, lines: Sequence[str], *, limit: int = 900) -> str:
    cleaned_blurb = blurb.strip()
    if not lines:
        return cleaned_blurb or "—"

    block = _join_and_truncate(lines, limit=limit)
    if cleaned_blurb:
        return f"{cleaned_blurb}\n{block}" if block else cleaned_blurb
    return block


def _join_and_truncate(lines: Sequence[str], limit: int = 900) -> str:
    if not lines:
        return "—"

    collected: list[str] = []
    total = 0
    for line in lines:
        text = line.rstrip()
        addition = len(text) + (1 if collected else 0)
        if collected and total + addition > limit:
            remaining = len(lines) - len(collected)
            if remaining > 0:
                collected.append(f"+{remaining} more…")
            break
        collected.append(text)
        total += addition

    return "\n".join(collected) if collected else "—"


def _build_section_chunks(
    prefix: str,
    label: str,
    commands: Sequence[HelpCommandInfo],
    *,
    show_empty: bool,
    limit: int = 800,
) -> list[tuple[str, str]]:
    entries = [command for command in commands if command]
    if not entries:
        if not show_empty:
            return []
        return [(label, "Coming soon")]

    lines: list[str] = []
    for command in entries:
        lines.extend(_format_overview_lines(prefix, command))

    chunks = _chunk_lines(lines, limit=limit)
    fields: list[tuple[str, str]] = []
    for index, chunk in enumerate(chunks):
        field_name = label if index == 0 else f"{label} (cont.)"
        fields.append((field_name, chunk))
    return fields


def _format_overview_lines(prefix: str, command: HelpCommandInfo) -> tuple[str, ...]:
    usage = command.usage_override or _format_usage(prefix, command.qualified_name, None)
    summary = command.short.strip() if command.short else "—"
    first_line = f"• `{usage}` — {summary}"
    lines: list[str] = [first_line]
    if command.flags:
        flags = ", ".join(flag.strip() for flag in command.flags if flag and flag.strip())
        if flags:
            lines.append(f"↳ flags: {flags}")
    return tuple(lines)


def _chunk_lines(lines: Sequence[str], *, limit: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0

    for line in lines:
        text = line.strip("\n")
        if not text:
            text = ""
        projected = current_len + (1 if current else 0) + len(text)
        if projected > limit and current:
            flush()
        if len(text) > limit:
            start = 0
            while start < len(text):
                end = min(start + limit, len(text))
                segment = text[start:end]
                if current:
                    flush()
                chunks.append(segment)
                start = end
            continue
        current.append(text)
        current_len = current_len + (1 if current_len and text else 0) + len(text)

    flush()
    return chunks or [""]
