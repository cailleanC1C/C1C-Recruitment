"""Core operational read-only helpers."""
from __future__ import annotations

from typing import Iterable

from discord.ext import commands

from shared.config import get_shared_config, redacted_items


def _format_tabs(tabs: Iterable[str]) -> str:
    tabs = list(dict.fromkeys(tabs))
    if not tabs:
        return "—"
    return ", ".join(sorted(tabs))


def build_config_summary(bot: commands.Bot | None = None) -> str:
    cfg = get_shared_config()
    items = redacted_items(cfg)
    tab_display = _format_tabs(cfg.enabled_tabs)
    allow_count = len(cfg.guild_ids)
    guild_noun = "guild" if allow_count == 1 else "guilds"
    cogs = sorted(bot.cogs.keys()) if bot is not None else []
    tabs_in_use = tab_display if tab_display != "—" else (", ".join(cogs) if cogs else "—")
    summary_lines = [
        f"env: {cfg.env_name}",
        f"guild allow-list: {allow_count} {guild_noun}",
        f"tabs in use: {tabs_in_use}",
    ]
    if items.get("LOG_CHANNEL_ID"):
        summary_lines.append(f"log channel: {items['LOG_CHANNEL_ID']}")
    summary_lines.append(f"command prefix: {cfg.command_prefix}")
    summary_lines.append(f"watchdog: {cfg.keepalive_interval_sec}s/{cfg.watchdog_stall_sec}s")
    summary_lines.append(f"discord token: {items['DISCORD_TOKEN']}")
    return "\n".join(summary_lines)


__all__ = ["build_config_summary"]
