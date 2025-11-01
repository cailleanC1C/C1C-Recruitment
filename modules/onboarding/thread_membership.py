"""Utilities for ensuring the bot has access to target threads."""

from __future__ import annotations

from typing import Tuple

import discord

__all__ = ["ensure_thread_membership"]


def _is_joined(thread: discord.Thread) -> bool:
    """Return ``True`` when the bot is already a member of ``thread``."""

    member = getattr(thread, "me", None)
    if member is None:
        return False

    joined = getattr(member, "joined", None)
    if joined is not None:
        return bool(joined)

    # Fallback: Discord may not expose ``joined`` on partial thread members.
    identifier = getattr(member, "id", None) or getattr(member, "user_id", None)
    return identifier is not None


async def ensure_thread_membership(thread: discord.Thread) -> Tuple[bool, BaseException | None]:
    """Ensure the bot has joined ``thread``.

    Returns a tuple ``(joined, error)`` where ``joined`` indicates whether the
    bot is a member after this call and ``error`` is the exception that occurred
    while attempting to join (if any).
    """

    if _is_joined(thread):
        return True, None

    join = getattr(thread, "join", None)
    if not callable(join):
        return False, None

    try:
        await join()
    except Exception as exc:  # pragma: no cover - exercised via unit tests
        return False, exc

    return True, None

