"""Helpers for emitting onboarding log messages to the shared log channel."""
from __future__ import annotations

import logging
from typing import Any

import discord

from modules.common import runtime as rt

__all__ = [
    "format_actor",
    "format_match",
    "format_parent",
    "format_thread",
    "send_welcome_log",
]

log = logging.getLogger("c1c.onboarding.logs")


def _format_payload(**kv: Any) -> str:
    parts: list[str] = []
    for key, value in kv.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)


def format_actor(actor: discord.abc.User | discord.Member | None) -> str:
    """Return a stable representation for actors in welcome logs."""

    if actor is None:
        return "<unknown>"
    actor_id = getattr(actor, "id", None)
    if actor_id is None:
        return "<unknown>"
    display = (
        getattr(actor, "display_name", None)
        or getattr(actor, "global_name", None)
        or getattr(actor, "name", None)
        or "user"
    )
    handle = f"@{display}".replace(" ", "_")
    return f"<{actor_id}|{handle}>"


def format_thread(thread_id: int | None) -> str | None:
    if thread_id is None:
        return None
    return f"<{thread_id}>"


def format_parent(parent_id: int | None) -> str | None:
    if parent_id is None:
        return None
    return f"<{parent_id}>"


def format_match(match: str | None) -> str | None:
    if match is None:
        return None
    return f"<{match}>"


async def send_welcome_log(level: str, **kv: Any) -> None:
    """Send a formatted welcome log message to the shared log channel."""

    payload = _format_payload(**kv)
    message = f"[welcome/{level}] {payload}" if payload else f"[welcome/{level}]"
    try:
        await rt.send_log_message(message)
    except Exception:  # pragma: no cover - defensive logging path
        log.warning("failed to send welcome log message", exc_info=True)
        log.info(message)
