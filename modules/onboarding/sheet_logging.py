from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import discord

from modules.onboarding import logs as onboarding_logs
from shared.config import get_admin_role_ids

T = TypeVar("T")

log = logging.getLogger("c1c.onboarding.sheet_logging")


def _format_actor(user: object | None) -> str:
    if user is None:
        return "<unknown>"
    if isinstance(user, str):
        text = user.strip() or "<unknown>"
        return text
    handle = onboarding_logs.format_actor_handle(user)
    if handle:
        return handle
    identifier = getattr(user, "id", None)
    return f"<{identifier}>" if identifier is not None else "<unknown>"


def _format_thread(thread: object | None) -> str:
    if thread is None:
        return "<unknown>"
    label = getattr(thread, "name", None) or getattr(thread, "id", None)
    if label:
        return str(label)
    return "<unknown>"


def _admin_ping() -> str:
    role_ids = sorted(get_admin_role_ids())
    if not role_ids:
        return ""
    return " ".join(f"<@&{rid}>" for rid in role_ids if rid)


async def log_sheet_write(
    *,
    flow: str,
    phase: str,
    tab: str,
    write_coro: Callable[[], Awaitable[T]],
    logger: logging.Logger | None = None,
    thread: discord.Thread | None = None,
    user: object | None = None,
) -> T:
    active_logger = logger or log
    thread_ref = _format_thread(thread)
    user_ref = _format_actor(user)
    base_fields = (
        f"flow={flow} • phase={phase} • tab={tab} "
        f"• thread={thread_ref} • user={user_ref}"
    )

    try:
        result = await write_coro()
    except Exception as exc:
        ping = _admin_ping()
        admin_suffix = f" {ping}" if ping else ""
        active_logger.error(
            "🧾 onboarding_sheet — sheet_update=failed • %s • error=%s%s",
            base_fields,
            exc,
            admin_suffix,
        )
        raise

    active_logger.info(
        "🧾 onboarding_sheet — sheet_update=ok • %s",
        base_fields,
    )
    return result
