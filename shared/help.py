# shared/help.py
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import List, Mapping, MutableMapping, Optional, Sequence

import discord
from discord.ext import commands

COREOPS_VERSION = "1.0.0"

_FIELD_LIMIT = 1024
_BULLET = "•"
_ELLIPSIS = "…"

_BOT_DESCRIPTION = (
    "Recruitment CoreOps keeps staffing teams informed with health signals, "
    "environment snapshots, and cache controls for day-to-day operations."
)


class AccessLevel(enum.IntEnum):
    USER = 0
    STAFF = 1
    ADMIN = 2


_SECTION_METADATA: Mapping[AccessLevel, tuple[str, str]] = {
    AccessLevel.USER: (
        "User",
        "Core status commands available to everyone.",
    ),
    AccessLevel.STAFF: (
        "Recruiter/Staff",
        "Operational tools for recruiters and staff leads.",
    ),
    AccessLevel.ADMIN: (
        "Admin",
        "High-scope administration and configuration actions.",
    ),
}


@dataclass(frozen=True)
class CommandSummary:
    command: commands.Command
    level: AccessLevel
    entry: str


class HelpLookupError(RuntimeError):
    """Raised when a help lookup fails."""


class HelpPermissionError(HelpLookupError):
    """Raised when a user requests help for a command they cannot access."""


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


async def build_help_embed(
    *,
    bot: commands.Bot,
    ctx: commands.Context,
    bot_name: str,
    prefix: str,
    bot_version: str,
    command_path: Sequence[str] | None = None,
) -> discord.Embed:
    """Build the dynamic help embed for the provided context."""

    query = " ".join(part.strip() for part in (command_path or []) if part.strip())
    if not query:
        summaries = await _collect_command_summaries(
            bot=bot,
            ctx=ctx,
            prefix=prefix,
        )
        return _build_overview_embed(
            bot_name=bot_name,
            prefix=prefix,
            bot_version=bot_version,
            summaries=summaries,
        )

    command = bot.get_command(query)
    if command is None:
        raise HelpLookupError(f"unknown command: {query}")

    if not await _command_is_accessible(command, ctx):
        raise HelpPermissionError(f"access denied for command: {query}")

    return await _build_command_embed(
        command=command,
        bot_name=bot_name,
        prefix=prefix,
        bot_version=bot_version,
        ctx=ctx,
    )


async def _collect_command_summaries(
    *, bot: commands.Bot, ctx: commands.Context, prefix: str
) -> List[CommandSummary]:
    bang_prefix = _format_prefix(prefix)
    summaries: List[CommandSummary] = []

    for command in sorted(bot.commands, key=lambda c: c.qualified_name):
        if command.hidden or not command.enabled:
            continue
        if command.parent is not None:
            continue

        if not await _command_is_accessible(command, ctx):
            continue

        level = _classify_command(command)
        summary_text = _format_summary_entry(command, bang_prefix)
        summaries.append(CommandSummary(command=command, level=level, entry=summary_text))

    return summaries


async def _command_is_accessible(command: commands.Command, ctx: commands.Context) -> bool:
    original_reply = getattr(ctx, "reply", None)

    async def _quiet_reply(*_args, **_kwargs):  # type: ignore[override]
        return None

    if original_reply is not None:
        setattr(ctx, "reply", _quiet_reply)
    try:
        return await command.can_run(ctx)
    except commands.CommandError:
        return False
    except Exception:
        return False
    finally:
        if original_reply is not None:
            setattr(ctx, "reply", original_reply)


def _classify_command(command: commands.Command) -> AccessLevel:
    level = AccessLevel.USER

    for check in getattr(command, "checks", ()):  # type: ignore[attr-defined]
        marker = _identify_check(check)
        if marker == "admin_only":
            return AccessLevel.ADMIN
        if marker in {"ops_only", "staff_only"}:
            level = max(level, AccessLevel.STAFF)

    return level


def _identify_check(check: object) -> Optional[str]:
    name = getattr(check, "__name__", "")
    qualname = getattr(check, "__qualname__", "")
    module = getattr(check, "__module__", "")
    descriptor = " ".join(filter(None, {name, qualname, module}))
    for marker in ("admin_only", "ops_only", "staff_only"):
        if marker in descriptor:
            return marker
    return None


def _format_summary_entry(command: commands.Command, bang_prefix: str) -> str:
    usage = _format_usage(command, bang_prefix)
    aliases = ""
    if command.aliases:
        rendered = ", ".join(f"`{alias}`" for alias in sorted(command.aliases))
        aliases = f" · aliases: {rendered}"
    summary = command.short_doc.strip() if command.short_doc else "No summary available."
    return f"{_BULLET} **{command.name}** — `{usage}`{aliases} · {summary}"


def _format_usage(command: commands.Command, bang_prefix: str) -> str:
    signature = command.signature.strip() if command.signature else ""
    if isinstance(command, commands.Group) and not signature:
        signature = "<subcommand>"
    qualified = command.qualified_name
    text = f"{bang_prefix} {qualified}".strip()
    if signature:
        text = f"{text} {signature}".strip()
    return text


def _build_overview_embed(
    *,
    bot_name: str,
    prefix: str,
    bot_version: str,
    summaries: Sequence[CommandSummary],
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{bot_name} · help",
        description=(
            f"{_BOT_DESCRIPTION}\n\n"
            f"Tip: Use `{_format_prefix(prefix)} help <command>` for an extended description."
        ),
        colour=discord.Colour.blurple(),
    )

    grouped: MutableMapping[AccessLevel, List[str]] = {
        level: [] for level in AccessLevel
    }
    for summary in summaries:
        grouped[summary.level].append(summary.entry)

    for level in AccessLevel:
        entries = grouped.get(level) or []
        if not entries:
            continue

        label, blurb = _SECTION_METADATA[level]
        lines = _truncate_entries(entries, limit=_FIELD_LIMIT)
        embed.add_field(
            name=label,
            value=f"{blurb}\n{lines}" if lines else blurb,
            inline=False,
        )

    embed.set_footer(text=build_coreops_footer(bot_version=bot_version))
    return embed


def _truncate_entries(entries: Sequence[str], *, limit: int) -> str:
    if not entries:
        return "—"

    rendered: List[str] = []
    remaining = len(entries)
    total = 0
    for index, entry in enumerate(entries):
        remaining = len(entries) - index - 1
        addition = len(entry) + (1 if rendered else 0)
        if total + addition > limit:
            if remaining >= 0:
                rendered.append(f"{_BULLET} +{remaining + 1} more{_ELLIPSIS}")
            break
        rendered.append(entry)
        total += addition

    return "\n".join(rendered) if rendered else "—"


async def _build_command_embed(
    *,
    command: commands.Command,
    bot_name: str,
    prefix: str,
    bot_version: str,
    ctx: commands.Context,
) -> discord.Embed:
    bang_prefix = _format_prefix(prefix)
    qualified = command.qualified_name
    title = f"{bot_name} · help · {qualified}"
    summary = command.help.strip() if command.help else command.short_doc.strip() if command.short_doc else "No summary available."

    embed = discord.Embed(title=title, description=summary, colour=discord.Colour.blurple())
    embed.add_field(name="Usage", value=f"`{_format_usage(command, bang_prefix)}`", inline=False)

    if command.aliases:
        alias_text = ", ".join(f"`{alias}`" for alias in sorted(command.aliases))
        embed.add_field(name="Aliases", value=alias_text, inline=False)

    if isinstance(command, commands.Group):
        sub_entries = await _collect_subcommand_entries(command, ctx, bang_prefix)
        if sub_entries:
            embed.add_field(
                name="Subcommands",
                value=_truncate_entries(sub_entries, limit=_FIELD_LIMIT),
                inline=False,
            )

    embed.set_footer(text=build_coreops_footer(bot_version=bot_version))
    return embed


async def _collect_subcommand_entries(
    command: commands.Group, ctx: commands.Context, bang_prefix: str
) -> List[str]:
    entries: List[str] = []
    for sub in sorted(command.commands, key=lambda c: c.qualified_name):
        if sub.hidden or not sub.enabled:
            continue
        if sub.parent is not command:
            continue
        if not await _command_is_accessible(sub, ctx):
            continue
        usage = _format_usage(sub, bang_prefix)
        summary_text = (
            sub.help.strip()
            if sub.help
            else sub.short_doc.strip()
            if sub.short_doc
            else "No summary available."
        )
        entries.append(f"{_BULLET} **{sub.name}** — `{usage}` · {summary_text}")
    return entries


def _format_prefix(prefix: str) -> str:
    prefix = prefix.strip()
    if prefix.startswith("!"):
        return prefix
    return f"!{prefix}" if prefix else "!"
