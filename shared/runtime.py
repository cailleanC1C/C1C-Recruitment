"""Application runtime scaffolding for the unified bot process."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, time as dt_time, timedelta
from typing import Awaitable, Callable, Iterable, Optional, Sequence

from aiohttp import web
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from discord.ext import commands

from shared import socket_heartbeat as hb
from shared import watchdog as watchdog_loop
from shared.config import (
    get_port,
    get_env_name,
    get_bot_name,
    get_keepalive_interval_sec,
    get_watchdog_check_sec,
    get_watchdog_stall_sec,
    get_watchdog_disconnect_grace_sec,
    get_log_channel_id,
    get_refresh_times,
    get_refresh_timezone,
)

log = logging.getLogger("c1c.runtime")


def _parse_times(parts: Iterable[str]) -> list[dt_time]:
    times: list[dt_time] = []
    for raw in parts:
        item = (raw or "").strip()
        if not item:
            continue
        try:
            hour_str, minute_str = item.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        except (ValueError, TypeError):
            log.warning("invalid refresh time entry skipped", extra={"entry": raw})
            continue
        if 0 <= hour < 24 and 0 <= minute < 60:
            times.append(dt_time(hour=hour, minute=minute))
        else:
            log.warning("refresh time out of range", extra={"entry": raw})
    # dedupe while preserving order
    seen: set[tuple[int, int]] = set()
    ordered: list[dt_time] = []
    for t in sorted(times):
        key = (t.hour, t.minute)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(t)
    return ordered


def _resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        log.warning("timezone not found; defaulting to UTC", extra={"timezone": name})
        return ZoneInfo("UTC")


def _next_run(now: datetime, schedule: Sequence[dt_time]) -> datetime:
    if not schedule:
        return now + timedelta(minutes=5)
    today = now.date()
    for entry in schedule:
        candidate = datetime.combine(today, entry, tzinfo=now.tzinfo)
        if candidate > now:
            return candidate
    tomorrow = today + timedelta(days=1)
    return datetime.combine(tomorrow, schedule[0], tzinfo=now.tzinfo)


def _trim_message(message: str, *, limit: int = 1800) -> str:
    message = message.strip()
    if len(message) <= limit:
        return message
    return f"{message[: limit - 1]}…"


class Scheduler:
    """Very small asyncio task supervisor for background jobs."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []

    def spawn(self, coro: Awaitable, *, name: Optional[str] = None) -> asyncio.Task:
        if name is not None:
            task = asyncio.create_task(coro, name=name)
        else:
            task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def shutdown(self) -> None:
        for task in self._tasks:
            if task.done():
                continue
            task.cancel()
        for task in self._tasks:
            if task.done():
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover - best-effort cleanup
                log.exception("scheduler task error during shutdown")


class Runtime:
    """Container object that wires the bot, health server, and scheduler."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.scheduler = Scheduler()
        self._web_app: Optional[web.Application] = None
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_params: Optional[tuple[int, int, int]] = None

    async def start_webserver(self, *, port: Optional[int] = None) -> None:
        if self._web_site is not None:
            return
        port = port or get_port()

        async def root(_: web.Request) -> web.Response:
            payload = {
                "ok": True,
                "bot": get_bot_name(),
                "env": get_env_name(),
                "version": os.getenv("BOT_VERSION", "dev"),
            }
            return web.json_response(payload)

        async def health(_: web.Request) -> web.Response:
            payload, healthy = await self._health_payload()
            payload["endpoint"] = "health"
            return web.json_response(payload, status=200 if healthy else 503)

        async def healthz(_: web.Request) -> web.Response:
            payload, healthy = await self._health_payload()
            payload["endpoint"] = "healthz"
            return web.json_response(payload, status=200 if healthy else 503)

        app = web.Application()
        app.router.add_get("/", root)
        app.router.add_get("/health", health)
        app.router.add_get("/healthz", healthz)

        self._web_app = app
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, host="0.0.0.0", port=port)
        await self._web_site.start()
        log.info("web server listening", extra={"port": port})

    async def _health_payload(self) -> tuple[dict, bool]:
        stall = get_watchdog_stall_sec()
        keepalive = get_keepalive_interval_sec()
        watchdog_check = get_watchdog_check_sec()
        snapshot = hb.snapshot()
        age = snapshot.last_event_age
        healthy = age <= stall
        payload = {
            "ok": healthy,
            "bot": get_bot_name(),
            "env": get_env_name(),
            "version": os.getenv("BOT_VERSION", "dev"),
            "age_seconds": round(age, 3),
            "stall_after_sec": stall,
            "keepalive_sec": keepalive,
            "watchdog_check_sec": watchdog_check,
            "connected": snapshot.connected,
            "disconnect_age": (
                None if snapshot.disconnect_age is None else round(snapshot.disconnect_age, 3)
            ),
            "last_ready_age": (
                None if snapshot.last_ready_age is None else round(snapshot.last_ready_age, 3)
            ),
        }
        return payload, healthy

    async def shutdown_webserver(self) -> None:
        site, runner = self._web_site, self._web_runner
        self._web_site = None
        self._web_runner = None
        self._web_app = None
        if site is not None:
            await site.stop()
        if runner is not None:
            await runner.cleanup()

    async def start_health_server(self) -> None:
        await self.start_webserver()

    async def shutdown_health_server(self) -> None:
        await self.shutdown_webserver()

    async def send_log_message(self, message: str) -> None:
        channel_id = get_log_channel_id()
        if not channel_id:
            return
        content = _trim_message(str(message))
        if not content:
            return
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                log.exception("failed to fetch log channel", extra={"channel_id": channel_id})
                return
        try:
            await channel.send(content)
        except Exception:
            log.exception("failed to send log message", extra={"channel_id": channel_id})

    def watchdog(
        self,
        *,
        check_sec: Optional[int] = None,
        stall_sec: Optional[int] = None,
        disconnect_grace: Optional[int] = None,
        delay_sec: float = 0.0,
    ) -> tuple[bool, int, int, int]:
        check = check_sec or get_watchdog_check_sec()
        stall = stall_sec or get_watchdog_stall_sec()
        disconnect = disconnect_grace or get_watchdog_disconnect_grace_sec(stall)

        task = self._watchdog_task
        if task is not None and not task.done():
            return False, check, stall, disconnect
        if task is not None and task.done():
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                exc = None
            if exc:
                log.error(
                    "previous watchdog task exited",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

        async def runner() -> None:
            if delay_sec > 0:
                await asyncio.sleep(delay_sec)
            await watchdog_loop.run(
                hb.age_seconds,
                stall_after_sec=stall,
                check_every=check,
                state_probe=hb.snapshot,
                disconnect_grace_sec=disconnect,
                latency_probe=lambda: getattr(self.bot, "latency", None),
            )

        self._watchdog_task = self.scheduler.spawn(runner(), name="watchdog")
        self._watchdog_params = (check, stall, disconnect)
        log.info(
            "watchdog loop started",
            extra={"interval": check, "stall": stall, "disconnect_grace": disconnect},
        )
        return True, check, stall, disconnect

    def schedule_at_times(
        self,
        callback: Callable[[], Awaitable[Optional[str]]],
        *,
        times: Optional[Iterable[str]] = None,
        timezone: Optional[str] = None,
        name: str = "scheduled_task",
    ) -> asyncio.Task:
        times_list = _parse_times(times or get_refresh_times())
        if not times_list:
            log.warning("no valid refresh times supplied; defaulting to hourly schedule")
            times_list = [dt_time(hour=0, minute=0)]
        tz_name = timezone or get_refresh_timezone()
        tz = _resolve_timezone(tz_name)

        async def runner() -> None:
            log.info(
                "scheduled runner active",
                extra={
                    "name": name,
                    "times": [f"{t.hour:02d}:{t.minute:02d}" for t in times_list],
                    "timezone": tz_name,
                },
            )
            while True:
                now = datetime.now(tz)
                next_at = _next_run(now, times_list)
                delay = max(1.0, (next_at - now).total_seconds())
                await asyncio.sleep(delay)
                try:
                    result = await callback()
                except Exception as exc:
                    log.exception("scheduled task error", extra={"name": name})
                    await self.send_log_message(f"❌ {name} failed: {exc}")
                else:
                    if result:
                        await self.send_log_message(str(result))

        return self.scheduler.spawn(runner(), name=name)

    async def load_extensions(self) -> None:
        """Load all feature modules into the shared bot instance."""

        from modules.coreops import cog as coreops_cog
        from recruitment import search as recruitment_search
        from recruitment import welcome as recruitment_welcome
        from onboarding import watcher_welcome as onboarding_welcome
        from onboarding import watcher_promo as onboarding_promo
        from ops import ops as ops_cog

        await coreops_cog.setup(self.bot)
        await recruitment_search.setup(self.bot)
        await recruitment_welcome.setup(self.bot)
        await onboarding_welcome.setup(self.bot)
        await onboarding_promo.setup(self.bot)
        await ops_cog.setup(self.bot)

    async def start(self, token: str) -> None:
        await self.start_webserver()
        await self.load_extensions()
        await self.bot.start(token)

    async def close(self) -> None:
        await self.shutdown_webserver()
        await self.scheduler.shutdown()
