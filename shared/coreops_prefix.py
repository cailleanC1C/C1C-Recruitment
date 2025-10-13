# shared/coreops_prefix.py
from __future__ import annotations

from copy import copy
from typing import Callable, Collection, Optional

import discord


AdminCheck = Callable[[discord.abc.User | discord.Member], bool]


def maybe_admin_coreops_message(
    message: discord.Message,
    *,
    prefix: str,
    commands: Collection[str],
    is_admin: AdminCheck,
) -> Optional[discord.Message]:
    """Return a synthetic message with the prefix injected for admin overrides."""

    if not commands or not callable(is_admin):
        return None
    if not is_admin(message.author):
        return None

    raw = (message.content or "").strip()
    if not raw:
        return None

    first_word = raw.split(None, 1)[0]
    lowered_commands = {cmd.lower() for cmd in commands}
    if first_word.lower() not in lowered_commands:
        return None

    rewritten = f"{prefix} {raw}".strip()
    clone = copy(message)
    # discord.py stores the dispatchable text on ``content``; make sure we update it
    # and bust any cached clean-content so the synthetic command is processed.
    clone.content = rewritten  # type: ignore[attr-defined]
    if hasattr(clone, "_clean_content"):
        clone._clean_content = None  # type: ignore[attr-defined]
    return clone
