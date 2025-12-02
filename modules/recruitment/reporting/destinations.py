from __future__ import annotations

"""Destination helpers for recruiter reports."""

import logging
import os
from typing import Optional

import discord

log = logging.getLogger("c1c.recruitment.reporting.destinations")


def get_report_destination_id() -> Optional[int]:
    raw = os.getenv("REPORT_RECRUITERS_DEST_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("invalid REPORT_RECRUITERS_DEST_ID=%r", raw)
        return None


async def resolve_report_destination(
    bot: discord.Client,
) -> tuple[Optional[discord.TextChannel | discord.Thread], str]:
    dest_id = get_report_destination_id()
    if not dest_id:
        return None, "dest-missing"

    await bot.wait_until_ready()

    try:
        channel = bot.get_channel(dest_id) or await bot.fetch_channel(dest_id)
    except Exception as exc:
        log.warning("failed to resolve report destination", exc_info=True)
        return None, f"dest:{type(exc).__name__}"

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return None, "dest-invalid"

    return channel, "-"


__all__ = ["get_report_destination_id", "resolve_report_destination"]
