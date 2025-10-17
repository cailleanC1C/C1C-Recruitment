# shared/help.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import discord

COREOPS_VERSION = "1.0.0"


@dataclass(frozen=True)
class HelpCommandInfo:
    """Immutable description of a command for help rendering."""

    qualified_name: str
    signature: str
    summary: str
    aliases: Sequence[str]


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
    sections: Sequence[tuple[str, Sequence[HelpCommandInfo]]],
    bot_version: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🌿C1C Recruitment Helper · help",
        colour=discord.Color.blurple(),
    )

    for label, commands in sections:
        if not commands:
            continue
        lines = [_format_summary_line(prefix, command) for command in commands]
        embed.add_field(name=label, value=_join_and_truncate(lines), inline=False)

    footer_text = build_coreops_footer(bot_version=bot_version)
    embed.set_footer(text=footer_text)
    return embed


def build_help_detail_embed(
    *,
    prefix: str,
    command: HelpCommandInfo,
    subcommands: Sequence[HelpCommandInfo],
    bot_version: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🌿C1C Recruitment Helper · help",
        colour=discord.Color.blurple(),
    )

    usage = _format_usage(prefix, command.qualified_name, command.signature)
    embed.add_field(name="Command", value=f"`{usage}`", inline=False)

    summary = command.summary.strip() if command.summary else "—"
    embed.add_field(name="Summary", value=summary or "—", inline=False)

    alias_text = _format_aliases(prefix, command.aliases)
    if alias_text:
        embed.add_field(name="Aliases", value=alias_text, inline=False)

    if subcommands:
        lines = [_format_summary_line(prefix, subcommand) for subcommand in subcommands]
        embed.add_field(
            name="Subcommands",
            value=_join_and_truncate(lines),
            inline=False,
        )

    footer_text = build_coreops_footer(bot_version=bot_version)
    embed.set_footer(text=footer_text)
    return embed


def _normalize_prefix(prefix: str) -> str:
    trimmed = prefix.strip()
    if not trimmed:
        return "!"
    return trimmed if trimmed.startswith("!") else f"!{trimmed}"


def _format_usage(prefix: str, qualified_name: str, signature: str | None) -> str:
    parts = [_normalize_prefix(prefix)]
    name = (qualified_name or "").strip()
    if name:
        parts.append(name)
    sig = (signature or "").strip()
    if sig:
        parts.append(sig)
    return " ".join(part for part in parts if part)


def _format_aliases(prefix: str, aliases: Iterable[str]) -> str:
    formatted = []
    for alias in aliases:
        alias_text = alias.strip()
        if not alias_text:
            continue
        formatted.append(f"`{_format_usage(prefix, alias_text, None)}`")
    if not formatted:
        return ""
    return f"(aliases: {', '.join(formatted)})"


def _format_summary_line(prefix: str, command: HelpCommandInfo) -> str:
    usage = _format_usage(prefix, command.qualified_name, command.signature)
    alias_text = _format_aliases(prefix, command.aliases)
    summary = command.summary.strip() if command.summary else "—"
    parts = [f"`{usage}`"]
    if alias_text:
        parts.append(alias_text)
    parts.append(f"— {summary}")
    return f"• {' '.join(parts)}"


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
                collected.append(f"… +{remaining} more")
            break
        collected.append(text)
        total += addition

    return "\n".join(collected) if collected else "—"
