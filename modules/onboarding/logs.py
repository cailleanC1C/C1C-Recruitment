"""Helpers for routing onboarding logs to the shared log channel."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Mapping

import discord

from modules.common import runtime as rt
from shared import logfmt

__all__ = [
    "format_actor",
    "format_actor_handle",
    "format_channel",
    "format_tag",
    "format_match",
    "format_parent",
    "format_thread",
    "thread_context",
    "send_welcome_log",
    "send_welcome_exception",
]

log = logging.getLogger("c1c.onboarding.logs")

_LOG_METHODS: dict[str, Callable[[str, Any], None]] = {}


def _resolve_logger(level: str) -> Callable[[str, Any], None]:
    """Return a logging function for the requested level."""

    if not _LOG_METHODS:
        _LOG_METHODS.update(
            {
                "debug": log.debug,
                "info": log.info,
                "warn": log.warning,
                "warning": log.warning,
                "error": log.error,
            }
        )
    return _LOG_METHODS.get(level, _LOG_METHODS["info"])

_ORDER = (
    "actor",
    "actor_name",
    "tag",
    "channel",
    "thread",
    "parent",
    "view",
    "result",
    "trigger",
    "flow",
    "source",
    "emoji",
    "reason",
    "schema",
    "questions",
    "details",
    "error",
)


def _format_payload(payload: Mapping[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for key in _ORDER:
        if key in payload and payload[key] is not None:
            parts.append(f"{key}={payload[key]}")
            seen.add(key)
    for key, value in payload.items():
        if key in seen or value is None:
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
    return f"<{actor_id}>"


def format_actor_handle(actor: discord.abc.User | discord.Member | None) -> str | None:
    if actor is None:
        return None
    display = (
        getattr(actor, "display_name", None)
        or getattr(actor, "global_name", None)
        or getattr(actor, "name", None)
        or None
    )
    if not display:
        return None
    handle = f"@{display}".replace(" ", "_")
    return handle


def format_channel(channel: discord.abc.GuildChannel | discord.Thread | None) -> str | None:
    if channel is None:
        return None
    guild = getattr(channel, "guild", None)
    identifier = getattr(channel, "id", None)
    return logfmt.channel_label(guild, identifier)


def _extract_thread_tag(thread: discord.Thread | None) -> str | None:
    if thread is None:
        return None
    applied = getattr(thread, "applied_tags", None)
    if applied:
        for tag in applied:
            name = getattr(tag, "name", None)
            if name:
                return str(name)
    name = getattr(thread, "name", "") or ""
    if name.startswith("[") and "]" in name:
        inner = name[1 : name.find("]")].strip()
        if inner:
            return inner
    return None


def format_tag(thread: discord.Thread | None) -> str | None:
    tag = _extract_thread_tag(thread)
    if tag:
        return f"<{tag}>"
    return "<unknown>"


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


def thread_context(thread: discord.Thread | None) -> dict[str, Any]:
    if thread is None:
        return {}
    return {
        "tag": format_tag(thread),
        "channel": format_channel(thread),
        "thread": format_thread(getattr(thread, "id", None)),
        "parent": format_channel(getattr(thread, "parent", None)),
    }


async def send_welcome_log(level: str, **kv: Any) -> None:
    """Send a formatted welcome log message to the shared log channel."""

    payload_map = dict(kv)
    payload = _format_payload(payload_map)
    message = f"[welcome/{level}] {payload}" if payload else f"[welcome/{level}]"
    logger = _resolve_logger(level)
    logger("%s", payload_map)
    try:
        await rt.send_log_message(message)
    except Exception:  # pragma: no cover - defensive logging path
        log.warning("failed to send welcome log message", exc_info=True)
        log.info(message)


async def send_welcome_exception(level: str, error: BaseException, **kv: Any) -> None:
    trace = "".join(traceback.format_exception(error))
    details = dict(kv)
    details.setdefault("result", "error")
    details["error"] = f"{error.__class__.__name__}: {error}"
    details["trace"] = trace
    await send_welcome_log(level, **details)
