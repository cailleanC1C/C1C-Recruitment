# shared/help.py
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


@dataclass(frozen=True)
class HelpCommandMetadata:
    """Curated copy for commands displayed in help embeds."""

    short: str
    detailed: str
    tier: str


def _metadata(short: str, detailed: str, tier: str) -> HelpCommandMetadata:
    return HelpCommandMetadata(short=short, detailed=detailed, tier=tier)


HELP_COMMAND_REGISTRY: dict[str, HelpCommandMetadata] = {
    # Admin Commands
    "config": _metadata(
        short="Shows the bot’s configuration and connected Sheets.",
        detailed=(
            "Displays which Google Sheets and tabs are currently linked, as defined in the Config tab. "
            "Helps confirm if all links are loaded correctly and readable.\n"
            "⚠️ If you type `config` without the prefix, **every bot** that has one may respond. "
            "Always use `!rec config` to target this bot.\n"
            "Tip: Run this after setup or when something seems out of sync."
        ),
        tier="admin",
    ),
    "digest": _metadata(
        short="Displays a quick system summary.",
        detailed=(
            "Generates a status digest with version, environment, cache stats, and sheet sync info. "
            "Useful for spotting stale data or delayed updates.\n"
            "⚠️ Running `digest` without `!rec` can trigger other bots’ digests too. Always include the prefix.\n"
            "Tip: Use this before reporting an issue — it’s the quick “what’s the bot doing?” check."
        ),
        tier="admin",
    ),
    "env": _metadata(
        short="Shows environment info (prod/test/etc.).",
        detailed=(
            "Reveals which environment the bot is running in and which guild IDs, tokens, and configs it’s currently using.\n"
            "⚠️ Calling `env` without `!rec` can wake multiple bots. Always include the prefix.\n"
            "Tip: Helps confirm you’re not running test commands in the live cluster."
        ),
        tier="admin",
    ),
    "health": _metadata(
        short="Checks bot’s health and cache freshness.",
        detailed=(
            "Runs internal health checks, showing cache ages, next refresh times, and Sheet latency. "
            "It’s the heartbeat command for admins.\n"
            "Tip: If values are old or “stale,” trigger a manual refresh."
        ),
        tier="admin",
    ),
    "rec env": _metadata(
        short="Shows environment info for this bot.",
        detailed=(
            "Displays which Sheets and tabs the bot is connected to, plus environment name and guild.\n"
            "Tip: Use when something feels “off” — it shows exactly what config is being read."
        ),
        tier="admin",
    ),
    "rec health": _metadata(
        short="Checks the bot’s internal health status.",
        detailed=(
            "Shows cache ages, refresh timings, and recent update status for all active data buckets.\n"
            "Tip: Run this if templates or lists aren’t updating as expected."
        ),
        tier="admin",
    ),
    "rec refresh": _metadata(
        short="Refreshes a single data bucket from Google Sheets.",
        detailed=(
            "Forces an update for one specific bucket — `templates`, `clansinfo`, or `clantags` — to reload new data from Sheets "
            "immediately instead of waiting for the next scheduled sync.\n"
            "Tip: Use `!rec refresh templates` after editing a Sheet tab."
        ),
        tier="admin",
    ),
    "rec refresh all": _metadata(
        short="Reloads all data from Sheets.",
        detailed=(
            "Performs a full refresh of every cached bucket — config, templates, clansinfo, and clantags. It can take a few seconds.\n"
            "Tip: Run this only after major sheet edits — not after every small change."
        ),
        tier="admin",
    ),
    "rec reload": _metadata(
        short="Reloads runtime configs and command modules.",
        detailed=(
            "Reloads the bot’s runtime flags and command modules without restarting it. Good for applying config changes instantly.\n"
            "Tip: Use after updating permissions or feature toggles."
        ),
        tier="admin",
    ),
    "refresh": _metadata(
        short="Manually refreshes a cache bucket.",
        detailed=(
            "Forces a refresh of shared caches used across the bot. Eligible buckets are `clansinfo`, `templates`, and `clantags`.\n"
            "Tip: Use only if you know which bucket you need — it applies cluster-wide."
        ),
        tier="admin",
    ),
    "reload": _metadata(
        short="Reloads core configuration and modules.",
        detailed=(
            "Reloads the bot’s entire runtime setup — environment variables, sheet connections, and commands. "
            "Use `--reboot` to force a soft reboot of the bot.\n"
            "⚠️ Running `reload` without `!rec` might make other bots react too. Always prefix it.\n"
            "Tip: Use with care — affects all modules, not just recruitment."
        ),
        tier="admin",
    ),
    # Recruiter/Staff Commands
    "checksheet": _metadata(
        short="Shows what sheet and tabs are currently loaded.",
        detailed=(
            "Displays the linked sheet and verifies that tabs (like `Applicants`, `Clans`, `Needs`) are cached and accessible.\n"
            "⚠️ If you use `checksheet` without the prefix, all bots with the same command will answer. Always use `!rec checksheet`.\n"
            "Tip: Quick sanity check before troubleshooting a missing clan."
        ),
        tier="admin",
    ),
    "rec checksheet": _metadata(
        short="Shows loaded tabs and headers.",
        detailed=(
            "Prints which tabs and headers the bot is reading, including row counts per tab.\n"
            "Tip: Use this after editing the Config tab to confirm it’s picked up."
        ),
        tier="staff",
    ),
    "rec config": _metadata(
        short="Shows current configuration values.",
        detailed=(
            "Displays all active configuration values — sheet IDs, refresh intervals, watcher toggles, and more.\n"
            "Tip: If behavior differs between prod and test, this command shows why."
        ),
        tier="staff",
    ),
    "rec digest": _metadata(
        short="Shows the bot’s status summary.",
        detailed=(
            "Lists key operational stats: cached sheet names, last refresh time, and update latency.\n"
            "Tip: Your go-to command before calling an admin."
        ),
        tier="staff",
    ),
    "rec refresh clansinfo": _metadata(
        short="Updates the clan info list.",
        detailed=(
            "Forces a refresh for the recruitment infos the `!clanmatch` panel uses, including open spots and clan requirements.\n"
            "Tip: Use right after a clan updates its recruitment data in Sheets."
        ),
        tier="staff",
    ),
    "welcome": _metadata(
        short="Posts a templated welcome message for a new recruit.",
        detailed=(
            "Pulls a pre-written message template from the cached `templates` bucket, replaces placeholders with the chosen clan’s tag "
            "(for example: `!welcome C1CE @player`), and posts it in the channel.\n"
            "Tip: Use the exact clan tag as in Sheets; tag the user directly."
        ),
        tier="staff",
    ),
    # User Commands
    "rec help": _metadata(
        short="Shows help for bot commands.",
        detailed=(
            "Lists all available commands or gives details for one specific command when you add its name.\n"
            "⚠️ Typing `help` without the prefix calls help from **all bots**. Always use `!rec help` for this one.\n"
            "Tip: Try `!rec help clansearch` for a how-to on that one."
        ),
        tier="user",
    ),
    "rec ping": _metadata(
        short="Checks if the bot is awake.",
        detailed=(
            "A simple test command that responds with “pong” to confirm the bot is online and responsive.\n"
            "⚠️ Using `ping` without `!rec` will make every active bot reply. Keep the prefix.\n"
            "Tip: If it doesn’t answer, the bot might be rebooting or down."
        ),
        tier="user",
    ),
}


def lookup_help_metadata(command_name: str) -> HelpCommandMetadata | None:
    """Return curated help metadata for the given command."""

    normalized = " ".join(command_name.lower().split())
    return HELP_COMMAND_REGISTRY.get(normalized)


@dataclass(frozen=True)
class HelpOverviewSection:
    """Collection of commands rendered together in the overview help embed."""

    label: str
    blurb: str
    commands: Sequence[HelpCommandInfo]


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


def _format_usage(prefix: str, qualified_name: str, signature: str | None) -> str:
    sig = (signature or "").strip()
    name = (qualified_name or "").strip()
    prefix_text = prefix or ""
    return f"{prefix_text}{name}{(' ' + sig) if sig else ''}"


def _format_summary_line(prefix: str, command: HelpCommandInfo) -> str:
    usage = _format_usage(prefix, command.qualified_name, None)
    summary = command.short.strip() if command.short else "—"
    return f"• `{usage}` — {summary}"


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
