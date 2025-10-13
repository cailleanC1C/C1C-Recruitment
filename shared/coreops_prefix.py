# shared/coreops_prefix.py
from __future__ import annotations

from copy import copy
import re
from typing import Callable, Collection, Optional
import discord

AdminCheck = Callable[[discord.abc.User | discord.Member], bool]
_BANG_CMD_RE = re.compile(r"^!\s*([a-zA-Z]+)(?:\s|$)")

def maybe_admin_bang_message(
    message: discord.Message,
    *, prefix: str, commands: Collection[str], is_admin: AdminCheck
) -> Optional[discord.Message]:
    if not commands or not callable(is_admin) or not is_admin(message.author):
        return None
    raw = (message.content or "").strip()
    m = _BANG_CMD_RE.match(raw)
    if not m:
        return None
    cmd = m.group(1).lower()
    if cmd not in {c.lower() for c in commands}:
        return None
    # Avoid double-prefix: ignore if it already starts with !<prefix>
    if raw.lower().startswith(f"!{prefix.lower()}"):
        return None
    rewritten = f"!{prefix} {raw[1:].lstrip()}"  # turn "!health" → "!rec health"
    clone = copy(message)
    clone._cs_content = rewritten  # discord.py cached content
    return clone
