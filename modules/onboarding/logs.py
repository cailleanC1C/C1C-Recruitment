"""Helpers for routing onboarding logs to the shared log channel."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Iterable, Mapping

import discord

from c1c_coreops.tags import lifecycle_tag
from modules.common import runtime as rt
from shared import logfmt
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
_PANEL_DEDUPER = EventDeduper()

_LOG_RECORD_RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }
)


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


def _sanitize_log_extra(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``payload`` that is safe for ``logging`` extras."""

    sanitized: dict[str, Any] = {}
    reserved_targets = set(payload)
    for key, value in payload.items():
        if key in _LOG_RECORD_RESERVED_ATTRS:
            alias_base = f"context_{key}"
            alias = alias_base
            suffix = 1
            while alias in sanitized or alias in reserved_targets:
                suffix += 1
                alias = f"{alias_base}_{suffix}"
            sanitized[alias] = value
        else:
            sanitized[key] = value
    return sanitized

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

    message = _render_payload(payload_map)
    if not message:
        return

    sanitized_extra = _sanitize_log_extra(payload_map)
    log_method = _resolve_logger(level)
    log_method("%s", sanitized_extra)

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
    details.setdefault("error", f"{error.__class__.__name__}: {error}")
    details["trace"] = trace
    await send_welcome_log(level, **details)


def log_view_error(
    interaction: discord.Interaction,
    view: discord.ui.View,
    err: BaseException,
    *,
    tag: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Emit a resilient error log for view callbacks.

    The Discord interaction payload frequently omits optional attributes. Guard
    every access so the logging path never raises and masks the original
    exception.
    """

    def _safe(getter: Callable[[], Any], default: Any = None) -> Any:
        try:
            return getter()
        except Exception:
            return default

    data = _safe(lambda: getattr(interaction, "data", None)) or {}
    response = getattr(interaction, "response", None)

    def _response_is_done() -> bool:
        if response is None:
            return False
        flag = getattr(response, "is_done", None)
        if callable(flag):
            return bool(_safe(flag, False))
        if flag is None:
            return False
        try:
            return bool(flag)
        except Exception:
            return False

    payload: dict[str, Any] = {
        "diag": "welcome_flow",
        "event": "view_error",
        "view": type(view).__name__,
        "view_tag": getattr(view, "tag", None) or tag or "unknown",
        "custom_id": _safe(lambda: data.get("custom_id")),
        "component_type": _safe(lambda: data.get("component_type")),
        "message_id": _safe(lambda: getattr(interaction.message, "id", None)),
        "interaction_id": _safe(lambda: getattr(interaction, "id", None)),
        "actor": str(_safe(lambda: getattr(interaction, "user", None))),
        "actor_id": _safe(lambda: getattr(getattr(interaction, "user", None), "id", None)),
        "actor_name": _safe(lambda: getattr(getattr(interaction, "user", None), "mention", None)),
        "response_is_done": _response_is_done(),
        "app_permissions": str(getattr(interaction, "app_permissions", None)),
        "claimed": getattr(interaction, "_c1c_claimed", False),
    }

    if extra:
        payload.update(extra)

    sanitized = _sanitize_log_extra(payload)
    sanitized.setdefault("error_class", err.__class__.__name__)
    sanitized.setdefault("error_message", str(err))

    try:
        log.error(
            "welcome view error",
            exc_info=(err.__class__, err, err.__traceback__),
            extra=sanitized,
        )
    except Exception:
        # As an extreme fallback emit a minimal record so the originating error
        # never disappears behind a logging failure.
        log.error(
            "welcome view error (minimal)",
            exc_info=(err.__class__, err, err.__traceback__),
            extra={"diag": "welcome_flow", "event": "view_error_min"},
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
    message: str | None
    if "tag" in payload and "recruit" in payload and "channel" in payload:
        details = payload.get("details")
        detail_items: list[str] = []
        if isinstance(details, Mapping):
            detail_items = [f"{key}={_stringify(value)}" for key, value in details.items()]
        elif isinstance(details, Iterable) and not isinstance(details, (str, bytes, bytearray)):
            detail_items = [_stringify(details)]
        elif details is not None:
            detail_items = [_stringify(details)]
        message = logfmt.LogTemplates.welcome(
            tag=_stringify(payload.get("tag")),
            recruit=_stringify(payload.get("recruit")),
            channel=_stringify(payload.get("channel")),
            result=_stringify(payload.get("result")),
            details=detail_items,
        )
    else:
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

        message = logfmt.LogTemplates.welcome_panel(
            actor=str(actor_display) if actor_display else "-",
            thread=thread_label,
            parent=parent_label if parent_label != "-" else None,
            result=result,
            details=detail_items,
        )

    if not message:
        return None
    return f"{lifecycle_tag()} {message}"
