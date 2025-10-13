# shared/coreops_prefix.py
from __future__ import annotations

import re
from typing import Callable, Collection, Dict, Optional

import discord

AdminCheck = Callable[[discord.abc.User | discord.Member], bool]
_BANG_CMD_RE = re.compile(r"^!\s*([a-zA-Z]+)(?:\s|$)")


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
    match = _BANG_CMD_RE.match(raw)
    if not match:
        return None
    cmd = match.group(1).lower()
    return normalized.get(cmd)
