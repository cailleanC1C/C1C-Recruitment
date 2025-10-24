# shared/coreops_prefix.py
from __future__ import annotations

from typing import Callable, Collection, Dict, Optional

import discord

__all__ = ["detect_admin_bang_command"]

AdminCheck = Callable[[discord.abc.User | discord.Member], bool]


def _normalize_commands(commands: Collection[str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for name in commands:
        if not isinstance(name, str):
            continue
        lowered = name.lower().strip()
        if lowered:
            lookup[lowered] = name
    return lookup


def detect_admin_bang_command(
    message: discord.Message,
    *, commands: Collection[str], is_admin: AdminCheck
) -> Optional[str]:
    normalized = _normalize_commands(commands)
    if not normalized or not callable(is_admin) or not is_admin(message.author):
        return None
    raw = (message.content or "").strip()
    if not raw.startswith("!"):
        return None
    trimmed = raw[1:].strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    for key, original in sorted(
        normalized.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if lowered == key or lowered.startswith(f"{key} "):
            return original
    return None
