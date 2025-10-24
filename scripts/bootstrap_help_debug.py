#!/usr/bin/env python3
"""Bootstrap CoreOps help debug artifacts without starting the bot."""

from __future__ import annotations

import asyncio
import os
from typing import Iterable

import discord
from discord.ext import commands

from c1c_coreops.cog import CoreOpsCog, _get_tier, _should_show
from config.runtime import get_bot_name, get_command_prefix
from shared.help import HelpOverviewSection, build_help_overview_embed, lookup_help_metadata


def _collect_sections(cog: CoreOpsCog) -> list[HelpOverviewSection]:
    grouped: dict[str, list[commands.Command]] = {"user": [], "staff": [], "admin": []}

    commands_iter: list[commands.Command] = []
    for command in cog.bot.walk_commands():
        if not _should_show(command):
            continue
        if not cog._include_in_overview(command):  # type: ignore[attr-defined]
            continue
        commands_iter.append(command)

    commands_iter.sort(key=lambda cmd: cmd.qualified_name)

    seen: set[str] = set()
    for command in commands_iter:
        base_name = command.qualified_name
        if base_name in seen:
            continue
        seen.add(base_name)
        level = _get_tier(command)
        metadata = (
            lookup_help_metadata(command.qualified_name)
            or lookup_help_metadata(command.name)
            or None
        )
        if metadata and metadata.tier:
            level = metadata.tier
        if level not in grouped:
            level = "user"
        grouped[level].append(command)

    tier_order: Iterable[tuple[str, str, str]] = (
        ("admin", "Admin", "Operational controls reserved for administrators."),
        (
            "staff",
            "Recruiter/Staff",
            "Tools for recruiters and staff managing applicant workflows.",
        ),
        ("user", "User", "Player-facing commands for everyday recruitment checks."),
    )

    seen.clear()
    sections: list[HelpOverviewSection] = []
    for key, label, blurb in tier_order:
        commands_for_tier = grouped.get(key, [])
        if not commands_for_tier:
            continue
        filtered: list[commands.Command] = []
        for command in sorted(commands_for_tier, key=lambda cmd: cmd.qualified_name):
            base_name = command.qualified_name
            if base_name in seen:
                continue
            seen.add(base_name)
            filtered.append(command)
        if not filtered:
            continue
        infos = [cog._build_help_info(command) for command in filtered]  # type: ignore[attr-defined]
        sections.append(
            HelpOverviewSection(label=label, blurb=blurb, commands=tuple(infos))
        )
    return sections


async def _main() -> None:
    intents = discord.Intents.none()
    bot = commands.Bot(command_prefix="!", intents=intents)
    cog = CoreOpsCog(bot)
    await bot.add_cog(cog)
    await cog.cog_load()

    try:
        from modules.coreops.helpers import rehydrate_tiers
    except Exception:
        rehydrate_tiers = None
    else:
        rehydrate_tiers(bot)

    sections = _collect_sections(cog)
    if not sections:
        return

    prefix = get_command_prefix()
    bot_name = get_bot_name()
    bot_version = os.getenv("BOT_VERSION", "dev")
    description = cog._help_bot_description(bot_name=bot_name)  # type: ignore[attr-defined]

    build_help_overview_embed(
        prefix=prefix,
        sections=sections,
        bot_version=bot_version,
        bot_name=bot_name,
        bot_description=description,
    )


if __name__ == "__main__":
    asyncio.run(_main())
