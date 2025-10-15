from __future__ import annotations

import asyncio
import datetime as dt

from .cache_service import cache
from .. import runtime as rt

UTC = dt.timezone.utc


async def _safe_refresh(bucket: str, *, trigger: str) -> None:
    try:
        await cache.refresh_now(bucket, trigger=trigger)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        await rt.send_log_message(
            f"[refresh] bucket={bucket} trigger={trigger} unexpected_error={exc}"
        )


async def _run_interval(bucket: str, interval_sec: int) -> None:
    while True:
        await _safe_refresh(bucket, trigger="schedule")
        await asyncio.sleep(interval_sec)


def _seconds_until_weekly(weekday: int, hour: int, minute: int) -> float:
    now = dt.datetime.now(UTC)
    target_date = now.date() + dt.timedelta(days=(weekday - now.weekday()) % 7)
    target = dt.datetime.combine(target_date, dt.time(hour=hour, minute=minute, tzinfo=UTC))
    if target <= now:
        target += dt.timedelta(days=7)
    return max(1.0, (target - now).total_seconds())


async def _run_weekly(bucket: str, *, weekday: int, hour: int, minute: int) -> None:
    while True:
        await asyncio.sleep(_seconds_until_weekly(weekday, hour, minute))
        await _safe_refresh(bucket, trigger="schedule")


def schedule_default_jobs(runtime: "rt.Runtime") -> None:
    if cache.get_bucket("clans") is None or cache.get_bucket("templates") is None:
        from sheets import recruitment  # noqa: F401  # ensures cache registration

    if cache.get_bucket("clan_tags") is None:
        from sheets import onboarding  # noqa: F401  # ensures cache registration

    runtime.scheduler.spawn(_run_interval("clans", 3 * 60 * 60), name="sheets_cache_clans")
    runtime.scheduler.spawn(
        _run_weekly("templates", weekday=0, hour=6, minute=0),
        name="sheets_cache_templates",
    )
    runtime.scheduler.spawn(
        _run_weekly("clan_tags", weekday=0, hour=6, minute=10),
        name="sheets_cache_clan_tags",
    )
