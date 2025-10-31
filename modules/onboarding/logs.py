"""Helpers for routing onboarding logs to the shared log channel."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Iterable, Mapping

import discord

from modules.common import runtime as rt
from shared import logfmt
from shared.config import get_log_dedupe_window_s
from shared.dedupe import EventDeduper

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
    "log_view_error",
]

log = logging.getLogger("c1c.onboarding.logs")

_LOG_METHODS: dict[str, Callable[[str, Any], None]] = {}
_PANEL_DEDUPER = EventDeduper(window_s=get_log_dedupe_window_s())


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

def _stringify(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        text = " ".join(value.split())
        return text or "-"
    if isinstance(value, Mapping):
        inner = ", ".join(f"{key}={_stringify(inner_value)}" for key, inner_value in value.items())
        return inner or "-"
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return ", ".join(_stringify(item) for item in value) or "-"
    return str(value)


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
    context: dict[str, Any] = {
        "tag": format_tag(thread),
        "channel": format_channel(thread),
        "thread": format_thread(getattr(thread, "id", None)),
        "parent": format_channel(getattr(thread, "parent", None)),
    }
    guild = getattr(thread, "guild", None)
    thread_id = getattr(thread, "id", None)
    parent = getattr(thread, "parent", None)
    parent_id = getattr(parent, "id", None)
    if thread_id is not None:
        context["thread_label"] = logfmt.channel_label(guild, thread_id)
    if parent_id is not None:
        context["channel_label"] = logfmt.channel_label(guild, parent_id)
    return context


async def send_welcome_log(level: str, **kv: Any) -> None:
    """Send a formatted welcome log message to the shared log channel."""

    payload_map = dict(kv)
    logger = _resolve_logger(level)
    logger("%s", payload_map)

    message = _render_payload(payload_map)
    if not message:
        return

    dedupe_key = _dedupe_key(payload_map)
    should_emit = True if dedupe_key is None else _PANEL_DEDUPER.should_emit(dedupe_key)
    if not should_emit:
        return

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


def log_view_error(extra: Mapping[str, Any] | None, err: BaseException) -> None:
    payload = dict(extra or {})
    log.error(
        "welcome view error",
        exc_info=(err.__class__, err, err.__traceback__),
        extra=payload,
    )


def _dedupe_key(payload: Mapping[str, Any]) -> str | None:
    if "tag" in payload and "recruit" in payload:
        return ":".join(
            str(part)
            for part in (
                "welcome_summary",
                payload.get("tag") or "-",
                payload.get("recruit") or "-",
                payload.get("result") or "-",
            )
        )
    thread_id = payload.get("thread_id") or payload.get("thread")
    message_id = payload.get("message_id")
    actor_id = payload.get("actor_id") or payload.get("actor")
    view_tag = payload.get("view_tag") or payload.get("view") or "welcome_panel"
    result = payload.get("result")
    if not result:
        return None
    return ":".join(
        str(part)
        for part in (
            view_tag,
            thread_id or "unknown",
            message_id or "-",
            actor_id or "-",
            result,
        )
    )


def _render_payload(payload: Mapping[str, Any]) -> str | None:
    if "tag" in payload and "recruit" in payload and "channel" in payload:
        details = payload.get("details")
        detail_items: list[str] = []
        if isinstance(details, Mapping):
            detail_items = [f"{key}={_stringify(value)}" for key, value in details.items()]
        elif isinstance(details, Iterable) and not isinstance(details, (str, bytes, bytearray)):
            detail_items = [_stringify(details)]
        elif details is not None:
            detail_items = [_stringify(details)]
        return logfmt.LogTemplates.welcome(
            tag=_stringify(payload.get("tag")),
            recruit=_stringify(payload.get("recruit")),
            channel=_stringify(payload.get("channel")),
            result=_stringify(payload.get("result")),
            details=detail_items,
        )

    actor_display = payload.get("actor_name") or _stringify(payload.get("actor"))
    thread_label = _stringify(
        payload.get("thread_label") or payload.get("channel") or payload.get("thread")
    )
    parent_label = _stringify(
        payload.get("channel_label") or payload.get("parent") or payload.get("parent_channel")
    )
    result = _stringify(payload.get("result"))

    detail_items: list[str] = []
    detail_fields = [
        ("view", ("view_tag", "view")),
        ("custom_id", ("custom_id",)),
        ("view_id", ("view_id",)),
        ("message", ("message_id",)),
        ("thread_id", ("thread_id",)),
        ("parent_id", ("parent_channel_id",)),
        ("actor_id", ("actor_id",)),
        ("target_user_id", ("target_user_id",)),
        ("target_message", ("target_message_id",)),
        ("app_perms_text", ("app_perms_text", "app_permissions")),
        ("missing", ("missing",)),
        ("trigger", ("trigger",)),
        ("source", ("source",)),
        ("reason", ("reason",)),
        ("schema", ("schema",)),
        ("questions", ("questions",)),
        ("emoji", ("emoji",)),
    ]
    for name, keys in detail_fields:
        value = None
        for key in keys:
            candidate = payload.get(key)
            if candidate is not None:
                value = candidate
                break
        if value is None:
            continue
        detail_items.append(f"{name}={_stringify(value)}")

    permissions_snapshot = payload.get("app_permissions_snapshot")
    if permissions_snapshot:
        detail_items.append(f"app_perms_flags={_stringify(permissions_snapshot)}")

    extra_details = payload.get("details")
    if isinstance(extra_details, Mapping):
        detail_items.extend(
            f"{key}={_stringify(value)}" for key, value in extra_details.items()
        )
    elif isinstance(extra_details, Iterable) and not isinstance(extra_details, (str, bytes, bytearray)):
        detail_items.append(_stringify(extra_details))
    elif extra_details is not None:
        detail_items.append(_stringify(extra_details))

    error_text = payload.get("error")
    if error_text:
        detail_items.append(f"error={_stringify(error_text)}")

    return logfmt.LogTemplates.welcome_panel(
        actor=str(actor_display) if actor_display else "-",
        thread=thread_label,
        parent=parent_label if parent_label != "-" else None,
        result=result,
        details=detail_items,
    )
