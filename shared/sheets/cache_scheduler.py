from __future__ import annotations

import asyncio
import datetime as dt
from typing import Awaitable, Callable, List

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


def _every_three_hours_utc() -> List[str]:
    return [f"{hour:02d}:00" for hour in range(0, 24, 3)]


def _if_monday(fn: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    async def _wrapped() -> None:
        now = dt.datetime.now(UTC)
        if now.weekday() == 0:  # Monday
            await fn()

    return _wrapped


def schedule_default_jobs(runtime: "rt.Runtime") -> None:
    if cache.get_bucket("clans") is None or cache.get_bucket("templates") is None:
        from sheets import recruitment  # noqa: F401  # ensures cache registration

    if cache.get_bucket("clan_tags") is None:
        from sheets import onboarding  # noqa: F401  # ensures cache registration

    runtime.schedule_at_times(
        lambda: _safe_refresh("clans", trigger="schedule"),
        times=_every_three_hours_utc(),
        timezone="UTC",
        name="sheets_cache_clans",
    )
    runtime.schedule_at_times(
        _if_monday(lambda: _safe_refresh("templates", trigger="schedule")),
        times=["06:00"],
        timezone="UTC",
        name="sheets_cache_templates",
    )
    runtime.schedule_at_times(
        _if_monday(lambda: _safe_refresh("clan_tags", trigger="schedule")),
        times=["06:10"],
        timezone="UTC",
        name="sheets_cache_clan_tags",
    )
