"""Diagnostic helpers for the welcome flow instrumentation."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable

import discord

log = logging.getLogger("c1c.onboarding.diag")

_RAW_FLAG = str(os.getenv("WELCOME_DIAG", "0")).strip().lower()
_DIAG_ENABLED = _RAW_FLAG in {"1", "true", "yes", "on"}

_LOG_PATH = Path(os.getenv("WELCOME_DIAG_PATH", "AUDIT/welcome_flow_diag.jsonl"))


def is_enabled() -> bool:
    """Return ``True`` when welcome-flow diagnostics should emit logs."""

    return _DIAG_ENABLED


def _ensure_log_dir() -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:  # pragma: no cover - defensive guard
        log.warning("failed to ensure diagnostic log directory", exc_info=True)


def _coerce_id(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean_value(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_clean_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _prepare_payload(event: str, fields: dict[str, Any]) -> dict[str, Any]:
    payload = {"diag": "welcome_flow", "event": event, "ts": time.time()}
    for key, value in fields.items():
        payload[key] = _clean_value(value)
    return payload


def _append_json_line(payload: dict[str, Any]) -> None:
    _ensure_log_dir()
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
    except Exception:  # pragma: no cover - defensive guard
        log.warning("failed to append welcome diag payload", exc_info=True)


async def log_event(level: str, event: str, **fields: Any) -> None:
    """Emit a diagnostic event to the JSON sink when enabled."""

    if not is_enabled():
        return

    payload = _prepare_payload(event, fields)
    _append_json_line(payload)


def log_event_sync(level: str, event: str, **fields: Any) -> None:
    """Emit a diagnostic event from synchronous contexts."""

    if not is_enabled():
        return

    payload = _prepare_payload(event, fields)
    _append_json_line(payload)


def permission_snapshot(
    interaction: discord.Interaction,
) -> tuple[dict[str, bool], str, Iterable[str]]:
    perms = getattr(interaction, "app_permissions", None)
    send_messages = bool(getattr(perms, "send_messages", False)) if perms is not None else False
    send_in_threads = (
        bool(getattr(perms, "send_messages_in_threads", False)) if perms is not None else False
    )
    embed_links = bool(getattr(perms, "embed_links", False)) if perms is not None else False
    read_history = bool(getattr(perms, "read_message_history", False)) if perms is not None else False

    snapshot = {
        "send_messages": send_messages,
        "send_messages_in_threads": send_in_threads,
        "embed_links": embed_links,
        "read_message_history": read_history,
    }

    missing: set[str] = set()
    if not send_messages:
        missing.add("send_messages")
    channel = getattr(interaction, "channel", None)
    if isinstance(channel, discord.Thread) and not send_in_threads:
        missing.add("send_messages_in_threads")

    formatted = ", ".join(f"{k}={v}" for k, v in snapshot.items())
    return snapshot, formatted, missing


def interaction_state(interaction: discord.Interaction) -> dict[str, Any]:
    """Return a normalized snapshot for ``interaction`` suitable for diagnostics."""

    message = getattr(interaction, "message", None)
    channel = getattr(interaction, "channel", None)
    thread_id = None
    parent_id = None
    if isinstance(channel, discord.Thread):
        thread_id = _coerce_id(getattr(channel, "id", None))
        parent_id = _coerce_id(getattr(channel, "parent_id", None))
    else:
        thread_id = _coerce_id(getattr(interaction, "channel_id", None))

    actor = getattr(interaction, "user", None)
    actor_id = _coerce_id(getattr(actor, "id", None))
    actor_roles: list[int] = []
    if isinstance(actor, discord.Member):
        for role in getattr(actor, "roles", []) or []:
            role_id = _coerce_id(getattr(role, "id", None))
            if role_id is not None:
                actor_roles.append(role_id)

    snapshot, formatted, missing = permission_snapshot(interaction)
    response_is_done = False
    try:
        response_is_done = bool(interaction.response.is_done())
    except Exception:  # pragma: no cover - defensive guard
        response_is_done = False

    followup_available = bool(getattr(interaction, "followup", None))

    state = {
        "message_id": _coerce_id(getattr(message, "id", None)),
        "thread_id": thread_id,
        "parent_id": parent_id,
        "actor_id": actor_id,
        "actor_roles": actor_roles,
        "response_is_done": response_is_done,
        "followup_available": followup_available,
        "app_permissions": snapshot,
        "app_permissions_text": formatted,
        "missing_permissions": sorted(missing),
    }
    return state


def relative_stack_site(frame_level: int = 1) -> str | None:
    try:
        import inspect

        frame = inspect.stack()[frame_level]
    except Exception:  # pragma: no cover - defensive guard
        return None

    filename = Path(frame.filename)
    try:
        repo_root = Path.cwd()
        filename = filename.relative_to(repo_root)
    except Exception:
        filename = Path(frame.filename)
    return f"{filename.as_posix()}:{frame.lineno}"

