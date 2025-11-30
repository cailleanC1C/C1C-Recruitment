from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

import discord
from discord.ext import commands

from modules.common import runtime as runtime_helpers
from shared.logfmt import channel_label

log = logging.getLogger("c1c.housekeeping.cleanup")

FOURTEEN_DAYS = timedelta(days=14)


def get_cleanup_interval_hours() -> int:
    """Return the configured cleanup cadence in hours (>=1)."""

    raw = os.getenv("CLEANUP_INTERVAL_HOURS")
    try:
        value = int(raw) if raw is not None else 24
    except (TypeError, ValueError):
        value = 24
    return max(1, value)


def get_cleanup_thread_ids() -> list[int]:
    """Return the configured list of thread IDs targeted by cleanup."""

    raw = os.getenv("CLEANUP_THREAD_IDS")
    if not raw:
        return []
    thread_ids: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            thread_ids.append(int(token))
        except (TypeError, ValueError):
            continue
    return thread_ids


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _resolve_thread(
    bot: commands.Bot, thread_id: int, logger: logging.Logger
) -> tuple[discord.Thread | None, int]:
    channel = bot.get_channel(thread_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(thread_id)
        except discord.NotFound:
            logger.warning(
                f"⚠️ **Cleanup** — reason=thread_not_found • thread_id={thread_id}",
                extra={"thread_id": thread_id, "reason": "thread_not_found"},
            )
            return None, 1
        except discord.Forbidden:
            logger.warning(
                f"⚠️ **Cleanup** — reason=missing_permissions • thread_id={thread_id}",
                extra={"thread_id": thread_id, "reason": "missing_permissions"},
            )
            return None, 1
        except discord.HTTPException as exc:
            logger.warning(
                f"⚠️ **Cleanup** — reason=fetch_failed • thread_id={thread_id}",
                extra={
                    "thread_id": thread_id,
                    "reason": "fetch_failed",
                    "error": str(exc),
                },
            )
            return None, 1
    if not isinstance(channel, discord.Thread):
        logger.warning(
            f"⚠️ **Cleanup** — reason=not_a_thread • thread_id={thread_id}",
            extra={"thread_id": thread_id, "reason": "not_a_thread"},
        )
        return None, 1
    return channel, 0


def _partition_messages(
    messages: Sequence[discord.Message], *, reference: datetime
) -> tuple[list[discord.Message], list[discord.Message]]:
    recent: list[discord.Message] = []
    older: list[discord.Message] = []
    for message in messages:
        created = _normalize_timestamp(message.created_at)
        if created is None:
            recent.append(message)
            continue
        if reference - created >= FOURTEEN_DAYS:
            older.append(message)
        else:
            recent.append(message)
    return recent, older


def _chunk_messages(items: Sequence[discord.Message], size: int = 100) -> Iterable[list[discord.Message]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


async def _delete_individual(
    messages: Sequence[discord.Message],
    *,
    reason: str,
    logger: logging.Logger,
) -> tuple[int, int]:
    deleted = 0
    errors = 0
    for message in messages:
        try:
            await message.delete(reason=reason)
        except discord.NotFound:
            continue
        except discord.Forbidden:
            logger.warning(
                f"⚠️ **Cleanup** — reason=missing_permissions • thread_id={message.channel.id}",
                extra={
                    "thread_id": getattr(message.channel, "id", None),
                    "reason": "missing_permissions",
                },
            )
            errors += 1
            break
        except discord.HTTPException as exc:
            logger.warning(
                f"⚠️ **Cleanup** — reason=delete_failed • thread_id={message.channel.id}",
                extra={
                    "thread_id": getattr(message.channel, "id", None),
                    "reason": "delete_failed",
                    "error": str(exc),
                },
            )
            errors += 1
            continue
        else:
            deleted += 1
    return deleted, errors


async def _cleanup_thread(thread: discord.Thread, logger: logging.Logger) -> tuple[int, int]:
    messages: list[discord.Message] = []
    try:
        async for message in thread.history(limit=None, oldest_first=True):
            if message.pinned:
                continue
            messages.append(message)
    except discord.Forbidden:
        logger.warning(
            f"⚠️ **Cleanup** — reason=missing_permissions • thread_id={thread.id}",
            extra={"thread_id": thread.id, "reason": "missing_permissions"},
        )
        return 0, 1
    except discord.HTTPException as exc:
        logger.warning(
            f"⚠️ **Cleanup** — reason=history_failed • thread_id={thread.id}",
            extra={
                "thread_id": thread.id,
                "reason": "history_failed",
                "error": str(exc),
            },
        )
        return 0, 1

    if not messages:
        return 0, 0

    now = datetime.now(timezone.utc)
    recent, older = _partition_messages(messages, reference=now)
    deleted = 0
    errors = 0

    for batch in _chunk_messages(recent, size=100):
        if len(batch) == 1:
            inc_deleted, inc_errors = await _delete_individual(
                batch, reason="panel cleanup", logger=logger
            )
            deleted += inc_deleted
            errors += inc_errors
            continue
        try:
            await thread.delete_messages(batch)
        except discord.HTTPException as exc:
            label = channel_label(thread.guild, thread.id)
            logger.warning(
                f"⚠️ **Cleanup** — reason=bulk_delete_failed • thread={label} • batch={len(batch)}",
                extra={
                    "thread_id": thread.id,
                    "reason": "bulk_delete_failed",
                    "batch_size": len(batch),
                    "error": str(exc),
                },
            )
            errors += 1
            inc_deleted, inc_errors = await _delete_individual(
                batch, reason="panel cleanup", logger=logger
            )
            deleted += inc_deleted
            errors += inc_errors
        else:
            deleted += len(batch)

    if older:
        inc_deleted, inc_errors = await _delete_individual(
            older, reason="panel cleanup", logger=logger
        )
        deleted += inc_deleted
        errors += inc_errors

    return deleted, errors


async def run_cleanup(bot: commands.Bot, logger: logging.Logger | None = None) -> None:
    logger = logger or log
    interval = get_cleanup_interval_hours()
    thread_ids = get_cleanup_thread_ids()

    total_deleted = 0
    errors = 0

    for thread_id in thread_ids:
        thread, resolution_errors = await _resolve_thread(bot, thread_id, logger)
        errors += resolution_errors
        if thread is None:
            continue
        deleted, thread_errors = await _cleanup_thread(thread, logger)
        total_deleted += deleted
        errors += thread_errors

    summary = (
        f"🧹 Cleanup — threads={len(thread_ids)} "
        f"• messages_deleted={total_deleted} • errors={errors}"
    )
    logger.info(summary)
    await runtime_helpers.send_log_message(summary)


__all__ = [
    "get_cleanup_interval_hours",
    "get_cleanup_thread_ids",
    "run_cleanup",
]
