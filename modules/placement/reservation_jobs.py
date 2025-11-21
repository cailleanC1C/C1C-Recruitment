"""Scheduled jobs that maintain clan seat reservations."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Awaitable, Callable

import discord
from discord.ext import commands

from modules.common import feature_flags
from modules.common import runtime as runtime_mod
from modules.common.logs import log as human_log
from modules.onboarding.watcher_welcome import (
    build_open_thread_name,
    parse_welcome_thread_name,
)
from modules.recruitment import availability
from shared.config import get_recruiter_role_ids, get_recruiters_thread_id
from shared.sheets import reservations

log = logging.getLogger(__name__)

_REMINDER_JOB_NAME = "reservations_reminder_daily"
_AUTORELEASE_JOB_NAME = "reservations_autorelease_daily"
_FEATURE_KEYS = ("FEATURE_RESERVATIONS", "feature_reservations", "placement_reservations")

_REMINDER_TASK: asyncio.Task | None = None
_AUTORELEASE_TASK: asyncio.Task | None = None


def _control_thread_hint() -> str:
    thread_id = get_recruiters_thread_id()
    if thread_id:
        return f"<#{thread_id}>"
    return "the recruiter control thread"


async def reservations_reminder_daily(
    *,
    bot: commands.Bot | None = None,
    today: dt.date | None = None,
) -> None:
    """Send reminder messages for reservations that expire today."""

    if not _reservations_enabled():
        log.debug("reservation reminder skipped (feature disabled)")
        return

    ledger: reservations.ReservationLedger
    try:
        ledger = await reservations.load_reservation_ledger()
    except Exception:
        log.exception("failed to load reservations ledger for reminder job")
        return

    current_date = today or dt.datetime.now(dt.timezone.utc).date()
    due_rows = [row for row in ledger.rows if row.is_active and row.reserved_until == current_date]
    if not due_rows:
        return

    active_bot = bot or _active_bot()
    if active_bot is None:
        log.warning("reservation reminder skipped (bot unavailable)")
        return

    await active_bot.wait_until_ready()

    recruiter_ping = _recruiter_ping()
    recompute_context: dict[str, discord.Guild | None] = {}

    for row in due_rows:
        thread = await _resolve_channel(active_bot, row.thread_id)
        clan_label = _display_tag(row.clan_tag)
        user_display = _user_display(row)
        until_display = _format_date(row.reserved_until)
        normalized_tag = _normalize_tag(row.clan_tag)
        thread_name = getattr(thread, "name", None) if thread is not None else None
        parts = parse_welcome_thread_name(thread_name) if thread_name else None
        ticket_code = parts.ticket_code if parts is not None else "unknown"
        username_label = parts.username if parts is not None else row.username_snapshot or user_display

        if normalized_tag and normalized_tag not in recompute_context:
            recompute_context[normalized_tag] = getattr(thread, "guild", None)

        if thread is None:
            log.warning(
                "reservation reminder thread missing",
                extra={"thread_id": row.thread_id, "clan_tag": clan_label},
            )
            human_log.human(
                "warning",
                "⚠️ reservation_reminder — ticket=%s • user=%s • clan=%s • expires=%s • result=error • reason=missing_channel"
                % (ticket_code, username_label, clan_label, until_display),
            )
            continue

        extend_example = (current_date + dt.timedelta(days=7)).isoformat()
        control_hint = _control_thread_hint()
        message_lines = [
            f"Reminder: The reserved spot in `{clan_label}` for {user_display} ends today.",
            "",
            f"• To keep this seat, head to {control_hint} and run `!reserve extend {user_display} {clan_label} {extend_example}`.",
            f"• To free it immediately, use {control_hint} and run `!reserve release {user_display} {clan_label}`.",
            "",
            "If you do nothing, I’ll release the seat automatically later today.",
        ]
        content = "\n".join(message_lines)
        if recruiter_ping:
            content = f"{recruiter_ping}\n{content}"

        try:
            await thread.send(content=content)
        except Exception:
            log.warning(
                "failed to send reservation reminder",
                exc_info=True,
                extra={"thread_id": row.thread_id, "clan_tag": clan_label},
            )
            human_log.human(
                "warning",
                "⚠️ reservation_reminder — ticket=%s • user=%s • clan=%s • expires=%s • result=error • reason=send_failed"
                % (ticket_code, username_label, clan_label, until_display),
            )
            continue

        human_log.human(
            "info",
            "🧭 reservation_reminder — ticket=%s • user=%s • clan=%s • expires=%s • result=notified"
            % (ticket_code, username_label, clan_label, until_display),
        )

    for clan_tag, guild in recompute_context.items():
        if not clan_tag:
            continue
        try:
            await availability.recompute_clan_availability(clan_tag, guild=guild)
        except Exception:
            log.exception(
                "failed to recompute availability after reminder",
                extra={"clan_tag": clan_tag},
            )


async def reservations_autorelease_daily(
    *,
    bot: commands.Bot | None = None,
    today: dt.date | None = None,
) -> None:
    """Expire overdue reservations and free seats automatically."""

    if not _reservations_enabled():
        log.debug("reservation auto-release skipped (feature disabled)")
        return

    ledger: reservations.ReservationLedger
    try:
        ledger = await reservations.load_reservation_ledger()
    except Exception:
        log.exception("failed to load reservations ledger for auto-release job")
        return

    status_column = ledger.status_column()
    current_date = today or dt.datetime.now(dt.timezone.utc).date()
    due_rows = [
        row
        for row in ledger.rows
        if row.is_active and row.reserved_until is not None and row.reserved_until <= current_date
    ]
    if not due_rows:
        return

    active_bot = bot or _active_bot()
    if active_bot is not None:
        await active_bot.wait_until_ready()
    else:
        log.warning("reservation auto-release proceeding without bot context")

    recruiters_thread = None
    recruiters_thread_id = get_recruiters_thread_id()
    if active_bot is not None and recruiters_thread_id:
        recruiters_thread = await _resolve_channel(active_bot, recruiters_thread_id)
        if recruiters_thread is None:
            log.warning(
                "recruiters summary thread missing",
                extra={"thread_id": recruiters_thread_id},
            )

    clan_context: dict[str, discord.Guild | None] = {}

    for row in due_rows:
        clan_label = _display_tag(row.clan_tag)
        user_display = _user_display(row)
        until_display = _format_date(row.reserved_until)

        try:
            await reservations.update_reservation_status(
                row.row_number,
                "expired",
                status_column=status_column,
            )
        except Exception:
            log.exception(
                "failed to mark reservation expired",
                extra={"row": row.row_number, "clan_tag": clan_label},
            )
            continue

        thread = await _resolve_channel(active_bot, row.thread_id) if active_bot is not None else None
        guild = getattr(thread, "guild", None)
        normalized_tag = _normalize_tag(row.clan_tag)
        if normalized_tag:
            clan_context.setdefault(normalized_tag, guild)

        if thread is not None:
            message = (
                f"The reserved spot in `{clan_label}` for {user_display} has expired and the seat has been released."
            )
            try:
                await thread.send(content=message)
            except Exception:
                log.warning(
                    "failed to post reservation expiry",
                    exc_info=True,
                    extra={"thread_id": row.thread_id, "clan_tag": clan_label},
                )
            await _reset_thread_name(thread)
        else:
            log.warning(
                "reservation expiry thread missing",
                extra={"thread_id": row.thread_id, "clan_tag": clan_label},
            )

        summary_line = (
            f"⚠️ Reservation expired — clan=`{clan_label}` • user=`{user_display}` • until=`{until_display}` • action=auto-release"
        )
        if recruiters_thread is not None:
            try:
                await recruiters_thread.send(content=summary_line)
            except Exception:
                log.warning(
                    "failed to post reservation expiry summary",
                    exc_info=True,
                    extra={"thread_id": recruiters_thread_id},
                )

        human_log.human(
            "info",
            "🧭 reservations-autorelease — clan=%s • user=%s • until=%s • result=expired"
            % (clan_label, user_display, until_display),
        )

    for clan_tag, guild in clan_context.items():
        try:
            await availability.recompute_clan_availability(clan_tag, guild=guild)
        except Exception:
            log.exception(
                "failed to recompute availability after auto-release",
                extra={"clan_tag": clan_tag},
            )


async def setup(bot: commands.Bot) -> None:
    """Register the reservation reminder and auto-release jobs."""

    runtime = runtime_mod.get_active_runtime()
    if runtime is None:
        log.warning("reservation jobs setup skipped (runtime unavailable)")
        return

    global _REMINDER_TASK, _AUTORELEASE_TASK

    if _REMINDER_TASK is None or _REMINDER_TASK.done():
        _REMINDER_TASK = runtime.scheduler.spawn(
            _daily_loop(12, 0, lambda: reservations_reminder_daily(bot=bot), _REMINDER_JOB_NAME),
            name=_REMINDER_JOB_NAME,
        )
        log.info("[cron] reservation reminder scheduler started (12:00Z)")

    if _AUTORELEASE_TASK is None or _AUTORELEASE_TASK.done():
        _AUTORELEASE_TASK = runtime.scheduler.spawn(
            _daily_loop(18, 0, lambda: reservations_autorelease_daily(bot=bot), _AUTORELEASE_JOB_NAME),
            name=_AUTORELEASE_JOB_NAME,
        )
        log.info("[cron] reservation auto-release scheduler started (18:00Z)")


def _reservations_enabled() -> bool:
    for key in _FEATURE_KEYS:
        try:
            if feature_flags.is_enabled(key):
                return True
        except Exception:
            log.exception("feature toggle check failed", extra={"feature": key})
    return False


def _active_bot() -> commands.Bot | None:
    runtime = runtime_mod.get_active_runtime()
    return runtime.bot if runtime is not None else None


def _daily_loop(
    hour: int,
    minute: int,
    job_factory: Callable[[], Awaitable[None]],
    job_name: str,
) -> Awaitable[None]:
    async def runner() -> None:
        while True:
            delay = _seconds_until(hour, minute)
            await asyncio.sleep(delay)
            try:
                await job_factory()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("reservation job failed", extra={"job": job_name})

    return runner()


def _seconds_until(hour: int, minute: int) -> float:
    now = dt.datetime.now(dt.timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target = target + dt.timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _recruiter_ping() -> str:
    role_ids = sorted(get_recruiter_role_ids())
    return " ".join(f"<@&{role_id}>" for role_id in role_ids if role_id)


async def _resolve_channel(
    bot: commands.Bot | None,
    channel_id: int | str | None,
) -> discord.abc.Messageable | None:
    if bot is None or not channel_id:
        return None
    snowflake = _to_int(channel_id)
    if snowflake is None:
        return None

    channel = bot.get_channel(snowflake)
    if channel is None:
        try:
            channel = await bot.fetch_channel(snowflake)
        except Exception:
            log.warning(
                "failed to fetch channel",
                exc_info=True,
                extra={"channel_id": snowflake},
            )
            return None

    if hasattr(channel, "send"):
        return channel  # type: ignore[return-value]
    return None


def _display_tag(tag: str | None) -> str:
    text = str(tag or "").strip()
    return text or "-"


def _normalize_tag(tag: str | None) -> str:
    text = str(tag or "").strip().upper()
    return "".join(ch for ch in text if ch.isalnum())


async def _reset_thread_name(thread: discord.Thread) -> None:
    name = getattr(thread, "name", None)
    parts = parse_welcome_thread_name(name)
    if parts is None or parts.state != "reserved":
        return

    new_name = build_open_thread_name(parts.ticket_code, parts.username)
    if not new_name or name == new_name:
        return

    try:
        await thread.edit(name=new_name)
    except Exception:
        log.warning(
            "failed to reset welcome thread name after reservation expiry",
            exc_info=True,
            extra={"thread_id": getattr(thread, "id", None), "ticket": parts.ticket_code},
        )


def _user_display(row: reservations.ReservationRow) -> str:
    if row.ticket_user_id:
        return f"<@{row.ticket_user_id}>"
    if row.username_snapshot:
        text = row.username_snapshot.strip()
        if text:
            return text
    if row.thread_id:
        return row.thread_id
    return "the recruit"


def _format_date(value: dt.date | None) -> str:
    return value.isoformat() if value else "-"


def _to_int(value: int | str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


__all__ = [
    "reservations_autorelease_daily",
    "reservations_reminder_daily",
    "setup",
]

