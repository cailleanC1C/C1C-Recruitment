from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Set

import discord
from discord.ext import commands

from modules.common import runtime as runtime_helpers
from shared.logfmt import channel_label

log = logging.getLogger("c1c.housekeeping.keepalive")


def _parse_id_set(key: str) -> Set[int]:
    raw = os.getenv(key)
    if not raw:
        return set()
    values: Set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.add(int(token))
        except (TypeError, ValueError):
            continue
    return values


def get_keepalive_channel_ids() -> set[int]:
    return _parse_id_set("KEEPALIVE_CHANNEL_IDS")


def get_keepalive_thread_ids() -> set[int]:
    return _parse_id_set("KEEPALIVE_THREAD_IDS")


def get_keepalive_interval_hours() -> int:
    raw = os.getenv("KEEPALIVE_INTERVAL_HOURS")
    try:
        value = int(raw) if raw is not None else 144
    except (TypeError, ValueError):
        value = 144
    return max(1, value)


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
                f"⚠️ Housekeeping: keepalive — reason=thread_not_found • thread_id={thread_id}",
                extra={"thread_id": thread_id, "reason": "thread_not_found"},
            )
            return None, 1
        except discord.Forbidden:
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=missing_permissions • thread_id={thread_id}",
                extra={"thread_id": thread_id, "reason": "missing_permissions"},
            )
            return None, 1
        except discord.HTTPException as exc:
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=fetch_failed • thread_id={thread_id}",
                extra={
                    "thread_id": thread_id,
                    "reason": "fetch_failed",
                    "error": str(exc),
                },
            )
            return None, 1
    if not isinstance(channel, discord.Thread):
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=not_a_thread • thread_id={thread_id}",
            extra={"thread_id": thread_id, "reason": "not_a_thread"},
        )
        return None, 1
    return channel, 0


async def _collect_channel_threads(
    bot: commands.Bot, channel_id: int, logger: logging.Logger
) -> tuple[Dict[int, discord.Thread], int]:
    errors = 0
    threads: Dict[int, discord.Thread] = {}
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.NotFound:
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=channel_not_found • channel_id={channel_id}",
                extra={"channel_id": channel_id, "reason": "channel_not_found"},
            )
            return threads, 1
        except discord.Forbidden:
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=missing_permissions • channel_id={channel_id}",
                extra={"channel_id": channel_id, "reason": "missing_permissions"},
            )
            return threads, 1
        except discord.HTTPException as exc:
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=fetch_failed • channel_id={channel_id}",
                extra={
                    "channel_id": channel_id,
                    "reason": "fetch_failed",
                    "error": str(exc),
                },
            )
            return threads, 1
    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=not_thread_host • channel_id={channel_id}",
            extra={"channel_id": channel_id, "reason": "not_thread_host"},
        )
        return threads, 1

    for thread in getattr(channel, "threads", []) or []:
        threads[thread.id] = thread

    async def _pull_archives(fetcher: Iterable[discord.Thread] | None) -> None:
        nonlocal errors
        if fetcher is None:
            return
        try:
            async for thread in fetcher:
                threads[thread.id] = thread
        except discord.Forbidden:
            label = channel_label(channel.guild, channel.id)
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=archived_forbidden • channel={label}",
                extra={"channel_id": channel_id, "reason": "archived_forbidden"},
            )
            errors += 1
        except discord.HTTPException as exc:
            label = channel_label(channel.guild, channel.id)
            logger.warning(
                f"⚠️ Housekeeping: keepalive — reason=archived_fetch_failed • channel={label}",
                extra={
                    "channel_id": channel_id,
                    "reason": "archived_fetch_failed",
                    "error": str(exc),
                },
            )
            errors += 1

    await _pull_archives(getattr(channel, "archived_threads", None) and channel.archived_threads(limit=None))
    private_fetcher = None
    if hasattr(channel, "archived_threads"):
        try:
            private_fetcher = channel.archived_threads(limit=None, private=True)
        except TypeError:
            private_fetcher = None
    if private_fetcher is None and hasattr(channel, "private_archived_threads"):
        private_fetcher = channel.private_archived_threads(limit=None)
    await _pull_archives(private_fetcher)

    return threads, errors


async def _get_bot_member(thread: discord.Thread, bot: commands.Bot) -> tuple[discord.Member | None, int]:
    if thread.guild is None or bot.user is None:
        return None, 1
    member = thread.guild.get_member(bot.user.id)
    if member:
        return member, 0
    try:
        member = await thread.guild.fetch_member(bot.user.id)
    except discord.Forbidden:
        return None, 1
    except discord.HTTPException:
        return None, 1
    return member, 0


async def _last_activity_at(thread: discord.Thread, logger: logging.Logger) -> tuple[datetime | None, int]:
    try:
        async for message in thread.history(limit=1):
            return _normalize_timestamp(message.created_at), 0
    except discord.Forbidden:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=history_forbidden • thread_id={thread.id}",
            extra={"thread_id": thread.id, "reason": "history_forbidden"},
        )
        return None, 1
    except discord.HTTPException as exc:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=history_failed • thread_id={thread.id}",
            extra={
                "thread_id": thread.id,
                "reason": "history_failed",
                "error": str(exc),
            },
        )
        return None, 1
    if thread.created_at:
        return _normalize_timestamp(thread.created_at), 0
    return None, 0


async def _post_heartbeat(thread: discord.Thread, logger: logging.Logger) -> tuple[bool, int]:
    try:
        await thread.send("🔹 Thread 💙-beat (housekeeping)")
    except discord.Forbidden:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=missing_permissions • thread_id={thread.id}",
            extra={"thread_id": thread.id, "reason": "missing_permissions"},
        )
        return False, 1
    except discord.HTTPException as exc:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=heartbeat_failed • thread_id={thread.id}",
            extra={
                "thread_id": thread.id,
                "reason": "heartbeat_failed",
                "error": str(exc),
            },
        )
        return False, 1
    return True, 0


async def _ensure_unarchived(thread: discord.Thread, logger: logging.Logger) -> int:
    if not thread.archived:
        return 0
    try:
        await thread.edit(archived=False)
    except discord.Forbidden:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=missing_permissions • thread_id={thread.id}",
            extra={"thread_id": thread.id, "reason": "missing_permissions"},
        )
        return 1
    except discord.HTTPException as exc:
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=unarchive_failed • thread_id={thread.id}",
            extra={
                "thread_id": thread.id,
                "reason": "unarchive_failed",
                "error": str(exc),
            },
        )
        return 1
    return 0


async def _process_thread(
    thread: discord.Thread,
    *,
    interval_hours: int,
    bot: commands.Bot,
    logger: logging.Logger,
) -> tuple[bool, int]:
    errors = 0
    member, perm_errors = await _get_bot_member(thread, bot)
    errors += perm_errors
    if member is None:
        return False, errors
    perms = thread.permissions_for(member)
    if not (perms.read_message_history and perms.send_messages and perms.manage_threads):
        logger.warning(
            f"⚠️ Housekeeping: keepalive — reason=insufficient_permissions • thread_id={thread.id}",
            extra={"thread_id": thread.id, "reason": "insufficient_permissions"},
        )
        return False, errors + 1

    last_activity, history_errors = await _last_activity_at(thread, logger)
    errors += history_errors
    if last_activity is None:
        return False, errors

    age_hours = (datetime.now(timezone.utc) - last_activity).total_seconds() / 3600.0
    if age_hours < interval_hours:
        return False, errors

    errors += await _ensure_unarchived(thread, logger)
    if thread.archived:
        return False, errors

    posted, post_errors = await _post_heartbeat(thread, logger)
    errors += post_errors
    return posted, errors


async def run_keepalive(bot: commands.Bot, logger: logging.Logger | None = None) -> None:
    logger = logger or log
    channel_ids = get_keepalive_channel_ids()
    explicit_thread_ids = get_keepalive_thread_ids()
    interval_hours = get_keepalive_interval_hours()

    errors = 0
    targets: Dict[int, discord.Thread] = {}

    for channel_id in channel_ids:
        channel_threads, channel_errors = await _collect_channel_threads(bot, channel_id, logger)
        errors += channel_errors
        targets.update(channel_threads)

    for thread_id in explicit_thread_ids:
        if thread_id in targets:
            continue
        thread, resolve_errors = await _resolve_thread(bot, thread_id, logger)
        errors += resolve_errors
        if thread is not None:
            targets[thread.id] = thread

    threads_touched = 0
    for thread in targets.values():
        posted, thread_errors = await _process_thread(
            thread, interval_hours=interval_hours, bot=bot, logger=logger
        )
        errors += thread_errors
        if posted:
            threads_touched += 1

    summary = (
        f"💙 Housekeeping: keepalive — threads_touched={threads_touched} "
        f"• errors={errors}"
    )
    logger.info(summary)
    await runtime_helpers.send_log_message(summary)


__all__ = [
    "get_keepalive_channel_ids",
    "get_keepalive_thread_ids",
    "get_keepalive_interval_hours",
    "run_keepalive",
]
