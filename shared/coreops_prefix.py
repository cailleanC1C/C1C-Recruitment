# shared/coreops_prefix.py
from __future__ import annotations

from copy import copy
import re
from typing import Callable, Collection, Optional
import discord

AdminCheck = Callable[[discord.abc.User | discord.Member], bool]
_BANG_CMD_RE = re.compile(r"^!\s*([a-zA-Z]+)(?:\s|$)")

def detect_admin_bang_command(
    message: discord.Message,
    *, commands: Collection[str], is_admin: AdminCheck
) -> Optional[str]:
    if not commands or not callable(is_admin) or not is_admin(message.author):
        return None
    raw = (message.content or "").strip()
    m = _BANG_CMD_RE.match(raw)
    if not m:
        return None
    cmd = m.group(1).lower()
    return cmd if cmd in {c.lower() for c in commands} else None
