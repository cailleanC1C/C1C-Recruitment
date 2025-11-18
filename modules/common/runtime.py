"""Application runtime scaffolding for the unified bot process."""

from __future__ import annotations

import asyncio
import importlib
import logging
import math
import os
import random
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence

from aiohttp import web
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from discord.ext import commands

from shared import health as healthmod
from shared import socket_heartbeat as hb
from shared import watchdog as watchdog_loop
from modules.common.logs import log as human_log
from shared import config as shared_config
from shared.config import (
    get_env_name,
    get_bot_name,
    get_watchdog_check_sec,
    get_watchdog_stall_sec,
    get_watchdog_disconnect_grace_sec,
    get_log_channel_id,
    get_refresh_times,
    get_refresh_timezone,
    get_strict_emoji_proxy,
)
from shared.ports import get_port
from shared.logging import get_trace_id, set_trace_id, setup_logging
from shared.obs.events import (
    format_refresh_message,
    refresh_bucket_results,
    refresh_dedupe_key,
    refresh_deduper,
)
from c1c_coreops.helpers import audit_tiers, rehydrate_tiers
from shared.web_routes import mount_emoji_pad
from . import keepalive

import modules.onboarding as onboarding_pkg

log = logging.getLogger("c1c.runtime")

_ACTIVE_RUNTIME: "Runtime | None" = None
_PRELOAD_TASK: asyncio.Task[None] | None = None
_web_app: web.Application | None = None


async def create_app(*, runtime: "Runtime | None" = None) -> web.Application:
    """Create and configure the aiohttp application used by the runtime."""

    static_fields = {"env": get_env_name(), "bot": get_bot_name()}
    access_logger = setup_logging(
        static_fields=static_fields,
        access_logger_name="aiohttp.access",
        access_static_fields={"env": static_fields["env"], "bot": static_fields["bot"]},
    )

    healthmod.set_component("runtime", True)

    @web.middleware
    async def tracing_middleware(
        request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
    ) -> web.StreamResponse:
        trace = set_trace_id()
        started = time.perf_counter()
        status = 500
        try:
            response = await handler(request)
            status = getattr(response, "status", status)
            try:
                response.headers["X-Trace-Id"] = trace
            except Exception:  # pragma: no cover - defensive guard
                pass
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            access_logger.info(
                "http_request",
                extra={
                    "trace": trace,
                    "path": request.path,
                    "method": request.method,
                    "status": status,
                    "ms": duration_ms,
                },
            )

    app = web.Application(middlewares=[tracing_middleware])

    mount_emoji_pad(app)
    strict_proxy_flag = "1" if get_strict_emoji_proxy() else "0"
    log.info("web: /emoji-pad mounted (STRICT_EMOJI_PROXY=%s)", strict_proxy_flag)

    async def root(_: web.Request) -> web.Response:
        payload = {
            "ok": True,
            "bot": get_bot_name(),
            "env": get_env_name(),
            "version": os.getenv("BOT_VERSION", "dev"),
            "trace": get_trace_id(),
        }
        return web.json_response(payload)

    async def ready(_: web.Request) -> web.Response:
        components = healthmod.components_snapshot()
        ok = healthmod.overall_ready()
        return web.json_response({"ok": ok, "components": components})

    async def _health_payload() -> tuple[dict[str, Any], bool]:
        if runtime is None:
            payload = {
                "ok": True,
                "bot": get_bot_name(),
                "env": get_env_name(),
                "version": os.getenv("BOT_VERSION", "dev"),
            }
            return payload, True
        return await runtime._health_payload()

    async def health(_: web.Request) -> web.Response:
        base_payload, healthy = await _health_payload()
        components = healthmod.components_snapshot()
        components_ok = all(item.get("ok", False) for item in components.values())
        ready_ok = healthmod.overall_ready()
        payload = dict(base_payload)
        payload.update(
            {
                "ok": bool(healthy and components_ok),
                "components": components,
                "ready": ready_ok,
                "endpoint": "health",
            }
        )
        status = 200 if payload["ok"] else 503
        return web.json_response(payload, status=status)

    async def healthz(_: web.Request) -> web.Response:
        payload, healthy = await _health_payload()
        payload = dict(payload)
        payload["endpoint"] = "healthz"
        status = 200 if healthy else 503
        return web.json_response(payload, status=status)

    async def _keepalive_handler(_: web.Request) -> web.Response:
        return web.Response(text="ok", status=200)

    app.router.add_get("/", root)
    app.router.add_get("/ready", ready)
    app.router.add_get("/health", health)
    app.router.add_get("/healthz", healthz)
    app.router.add_get(keepalive.route_path(), _keepalive_handler)

    return app


async def _startup_preload(bot: commands.Bot | None = None) -> None:
    await asyncio.sleep(15)

    runtime = get_active_runtime()
    if bot is None and runtime is not None:
        bot = runtime.bot

    if bot is None:  # pragma: no cover - defensive guard
        log.warning("Cache preloader aborted: bot unavailable")
        return

    from shared.cache import telemetry as cache_telemetry
    from c1c_coreops.render import RefreshEmbedRow

    bucket_names = cache_telemetry.list_buckets()
    if not bucket_names:
        log.info("Cache preloader skipped: no cache buckets registered")
        return

    rows: list[RefreshEmbedRow] = []
    total_ms = 0
    fallback_lines: list[str] = []
    refresh_results: list[cache_telemetry.RefreshResult] = []

    for name in bucket_names:
        try:
            result = await cache_telemetry.refresh_now(
                name=name,
                actor="startup",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            log.exception("startup preload refresh failed", extra={"bucket": name})
            await send_log_message(f"❌ Startup refresh failed for {name}: {exc}")
            continue

        snapshot = result.snapshot
        duration_ms = result.duration_ms or 0
        total_ms += duration_ms

        raw_result = snapshot.last_result or ("ok" if result.ok else "fail")
        display_result = raw_result.replace("_", " ").strip() or "-"
        normalized = raw_result.lower()
        retries_flag = "1" if normalized in {"retry_ok", "fail"} else "0"

        error_text = result.error or snapshot.last_error or "-"
        cleaned_error = " ".join(str(error_text).split()) if error_text else "-"
        if len(cleaned_error) > 70:
            cleaned_error = f"{cleaned_error[:67]}…"

        label = name or "-"
        ttl_display = "?"
        if snapshot.ttl_expired is True:
            ttl_display = "yes"
        elif snapshot.ttl_expired is False:
            ttl_display = "no"

        count_display = "-"
        if snapshot.item_count is not None:
            count_display = str(snapshot.item_count)

        refresh_results.append(result)

        rows.append(
            RefreshEmbedRow(
                bucket=label,
                duration=f"{duration_ms} ms",
                result=display_result,
                retries=retries_flag,
                ttl_expired=ttl_display,
                count=count_display,
                error=cleaned_error or "-",
            )
        )

        fallback_lines.append(
            f"{label}: {display_result} · {duration_ms} ms · error={cleaned_error or '-'}"
        )

    if not rows:
        log.info("Cache preloader completed with no rows")
        return

    deduper = refresh_deduper()
    bucket_names_for_key = [res.name or name for res, name in zip(refresh_results, bucket_names)]
    key = refresh_dedupe_key("startup", None, bucket_names_for_key)
    if refresh_results and deduper.should_emit(key):
        buckets_for_message = refresh_bucket_results(refresh_results)
        await send_log_message(
            format_refresh_message("startup", buckets_for_message, total_s=total_ms / 1000.0)
        )

    log.info("Cache preloader completed")


def set_active_runtime(runtime: "Runtime | None") -> None:
    """Set the active runtime used by module-level helpers."""

    global _ACTIVE_RUNTIME
    _ACTIVE_RUNTIME = runtime


def get_active_runtime() -> "Runtime | None":
    """Return the active runtime instance if one has been registered."""

    return _ACTIVE_RUNTIME


def schedule_startup_preload(bot: commands.Bot | None = None) -> None:
    """Ensure the startup cache preload task has been scheduled."""

    global _PRELOAD_TASK
    task = _PRELOAD_TASK
    if task is not None and not task.done():
        return
    if task is not None and task.done():
        try:  # pragma: no cover - defensive logging
            task.result()
        except Exception:
            log.debug("previous cache preloader task completed with error", exc_info=True)
    _PRELOAD_TASK = asyncio.create_task(
        _startup_preload(bot), name="cache_startup_preload"
    )


async def send_log_message(message: str) -> None:
    """Proxy to the active runtime's log channel helper, if available."""

    runtime = get_active_runtime()
    if runtime is None:
        return
    await runtime.send_log_message(message)


async def recreate_http_app() -> None:
    """Restart the aiohttp application when an active runtime is available."""

    runtime = get_active_runtime()
    if runtime is None:
        log.debug("recreate_http_app skipped: no active runtime")
        return
    await runtime.shutdown_webserver()
    await runtime.start_webserver()


def monotonic_ms() -> int:
    """Return a monotonic millisecond timestamp for lightweight timing."""

    return int(time.monotonic() * 1000)


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


class _RecurringJob:
    def __init__(
        self,
        scheduler: "Scheduler",
        *,
        interval: timedelta,
        jitter: str | float | None = None,
        tag: str | None = None,
        name: str | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._interval = interval
        self._jitter = jitter
        self.tag = tag
        self.name = name
        self.next_run: datetime | None = None

    def _pick_jitter(self) -> float:
        if self._jitter == "small":
            window = min(60.0, self._interval.total_seconds() * 0.05)
            if window <= 0:
                return 0.0
            return random.uniform(-window, window)
        if isinstance(self._jitter, (int, float)):
            window = abs(float(self._jitter))
            if window <= 0:
                return 0.0
            return random.uniform(-window, window)
        return 0.0

    def _compute_next_run(self, reference: datetime | None = None) -> datetime:
        now = reference or datetime.now(timezone.utc)
        interval_seconds = max(1.0, self._interval.total_seconds())
        # Align to UTC boundaries with optional jitter.
        cycles = math.floor(now.timestamp() / interval_seconds)
        base_seconds = (cycles + 1) * interval_seconds
        candidate = datetime.fromtimestamp(base_seconds, tz=timezone.utc)
        jitter_offset = self._pick_jitter()
        if jitter_offset:
            candidate = candidate + timedelta(seconds=jitter_offset)
        if candidate <= now:
            candidate = now + timedelta(seconds=1)
        return candidate

    async def _sleep_until_due(self) -> None:
        if self.next_run is None:
            self.next_run = self._compute_next_run()
        while True:
            assert self.next_run is not None
            now = datetime.now(timezone.utc)
            delay = (self.next_run - now).total_seconds()
            if delay <= 0:
                break
            await asyncio.sleep(min(delay, 60.0))

    def do(self, job: Callable[[], Awaitable[None]]) -> asyncio.Task:
        self.next_run = self._compute_next_run()

        async def runner() -> None:
            while True:
                await self._sleep_until_due()
                try:
                    await job()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception(
                        "recurring job error",
                        extra={
                            "job_name": self.name or getattr(job, "__name__", "job"),
                            "tag": self.tag,
                        },
                    )
                finally:
                    self.next_run = self._compute_next_run()

        task_name = self.name or getattr(job, "__name__", "recurring_job")
        return self._scheduler.spawn(runner(), name=task_name)


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

    def every(
        self,
        *,
        hours: float = 0.0,
        minutes: float = 0.0,
        seconds: float = 0.0,
        jitter: str | float | None = None,
        tag: str | None = None,
        name: str | None = None,
    ) -> _RecurringJob:
        total_seconds = float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)
        if total_seconds <= 0:
            total_seconds = 60.0
        interval = timedelta(seconds=total_seconds)
        return _RecurringJob(self, interval=interval, jitter=jitter, tag=tag, name=name)

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
        set_active_runtime(self)

    async def start_webserver(self, *, port: Optional[int] = None) -> None:
        if self._web_site is not None:
            return
        port = port or get_port()

        global _web_app
        if _web_app is not None:
            try:
                await _web_app.shutdown()
            except Exception:
                pass
            try:
                await _web_app.cleanup()
            except Exception:
                pass
            _web_app = None

        app = await create_app(runtime=self)

        self._web_app = app
        _web_app = app
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, host="0.0.0.0", port=port)
        await self._web_site.start()
        human_log.human("info", f"web server listening • port={port}")
        log.info("web server listening", extra={"port": port})

    async def _health_payload(self) -> tuple[dict, bool]:
        stall = get_watchdog_stall_sec()
        keepalive = get_watchdog_check_sec()
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
        site, runner, app = self._web_site, self._web_runner, self._web_app
        self._web_site = None
        self._web_runner = None
        self._web_app = None
        global _web_app
        if _web_app is app:
            _web_app = None
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

    def schedule_startup_preload(self) -> None:
        schedule_startup_preload(self.bot)

    def watchdog(
        self,
        *,
        check_sec: Optional[int] = None,
        stall_sec: Optional[int] = None,
        disconnect_grace: Optional[int] = None,
        delay_sec: float = 0.0,
    ) -> tuple[bool, int, int, int]:
        check = check_sec if check_sec is not None else get_watchdog_check_sec()
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
                    log.exception("scheduled task error", extra={"job_name": name})
                    await self.send_log_message(f"❌ {name} failed: {exc}")
                else:
                    if result:
                        await self.send_log_message(str(result))

        return self.scheduler.spawn(runner(), name=name)

    async def load_extensions(self) -> None:
        """Load all feature modules into the shared bot instance."""

        from c1c_coreops import cog as coreops_cog
        from cogs import app_admin
        from modules.onboarding import ops_check as onboarding_ops_check
        from modules.onboarding import reaction_fallback as onboarding_reaction_fallback
        from modules.onboarding import watcher_welcome as onboarding_welcome
        from modules.onboarding import watcher_promo as onboarding_promo
        from modules.onboarding import cmd_resume as onboarding_cmd_resume
        from modules.ops import permissions_sync as ops_permissions
        from modules.ops import watchers_permissions as ops_watchers
        from c1c_coreops import ops as ops_cog

        await coreops_cog.setup(self.bot)
        await app_admin.setup(self.bot)

        from modules.common import feature_flags as features

        try:
            await features.refresh()
        except Exception:
            log.exception("feature toggle refresh failed")
        else:
            try:
                shared_config.update_feature_flags_snapshot(features.values())
            except Exception:
                log.exception("feature toggle snapshot update failed")

        await onboarding_pkg.setup(self.bot)

        async def _load_feature_module(
            module_path: str, feature_keys: Sequence[str]
        ) -> None:
            enabled_keys = [key for key in feature_keys if features.is_enabled(key)]
            if not enabled_keys:
                extra_info = {
                    "feature_module": module_path,
                    "feature_keys": list(feature_keys),
                }
                if len(extra_info["feature_keys"]) == 1:
                    extra_info["feature_key"] = extra_info["feature_keys"][0]
                log.info(
                    "feature toggles disabled; skipping module",
                    extra=extra_info,
                )
                return

            try:
                module = importlib.import_module(module_path)
            except Exception as exc:  # pragma: no cover - defensive guard
                extra_info = {
                    "feature_module": module_path,
                    "feature_keys": enabled_keys,
                }
                if len(extra_info["feature_keys"]) == 1:
                    extra_info["feature_key"] = extra_info["feature_keys"][0]
                log.exception(
                    "failed to import feature module",
                    extra=extra_info,
                )
                try:
                    await self.send_log_message(
                        f"❌ Failed to import {module_path}: {exc}"
                    )
                except Exception:
                    pass
                return

            setup = getattr(module, "setup", None)
            if setup is None:
                extra_info = {
                    "feature_module": module_path,
                    "feature_keys": enabled_keys,
                }
                if len(extra_info["feature_keys"]) == 1:
                    extra_info["feature_key"] = extra_info["feature_keys"][0]
                log.warning(
                    "feature module missing setup()",
                    extra=extra_info,
                )
                return

            try:
                result = setup(self.bot)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # pragma: no cover - defensive guard
                extra_info = {
                    "feature_module": module_path,
                    "feature_keys": enabled_keys,
                }
                if len(extra_info["feature_keys"]) == 1:
                    extra_info["feature_key"] = extra_info["feature_keys"][0]
                log.exception(
                    "feature module setup failed",
                    extra=extra_info,
                )
                try:
                    await self.send_log_message(
                        f"❌ {module_path}.setup failed: {exc}"
                    )
                except Exception:
                    pass
                return

            extra_info = {
                "feature_module": module_path,
                "feature_keys": enabled_keys,
            }
            if len(extra_info["feature_keys"]) == 1:
                extra_info["feature_key"] = extra_info["feature_keys"][0]
            log.info(
                "feature module loaded",
                extra=extra_info,
            )

        await _load_feature_module(
            "modules.recruitment.services.search", ("member_panel", "recruiter_panel")
        )
        await _load_feature_module("cogs.recruitment_member", ("member_panel",))
        await _load_feature_module("cogs.recruitment_recruiter", ("recruiter_panel",))

        if features.is_enabled("clan_profile"):
            from cogs import recruitment_clan_profile

            await recruitment_clan_profile.setup(self.bot)
            log.info("modules: clan_profile enabled")
        else:
            log.info("modules: clan_profile disabled")
        await _load_feature_module(
            "cogs.recruitment_welcome", ("recruitment_welcome",)
        )
        await _load_feature_module(
            "modules.recruitment.reports", ("recruitment_reports",)
        )
        await _load_feature_module(
            "modules.placement.target_select", ("placement_target_select",)
        )
        await _load_feature_module(
            "modules.placement.reservations",
            ("feature_reservations", "placement_reservations"),
        )
        await _load_feature_module(
            "modules.placement.reservation_jobs",
            ("feature_reservations", "placement_reservations"),
        )

        await onboarding_ops_check.setup(self.bot)
        await onboarding_reaction_fallback.setup(self.bot)
        await onboarding_welcome.setup(self.bot)
        await onboarding_promo.setup(self.bot)
        await onboarding_cmd_resume.setup(self.bot)  # registers !onb resume
        await ops_cog.setup(self.bot)
        await ops_permissions.setup(self.bot)
        await ops_watchers.setup(self.bot)

        # === Always-on internal extensions (admin-gated debug/ops commands) ===
        ALWAYS_EXTENSIONS = (
            "modules.coreops.cmd_cfg",
            "modules.community.shard_tracker",
        )
        for ext in ALWAYS_EXTENSIONS:
            try:
                await self.bot.load_extension(ext)
            except Exception as exc:
                human_log.human(
                    "warn",
                    "feature module load failed",
                    feature_module=ext,
                    feature_key="always_on",
                    error=str(exc),
                )
            else:
                human_log.human(
                    "info",
                    "feature module loaded",
                    feature_module=ext,
                    feature_key="always_on",
                )

        # (Refresh commands now live directly in the CoreOps cog.)

    async def start(self, token: str) -> None:
        await self.start_webserver()
        await self.load_extensions()
        rehydrate_tiers(self.bot)
        audit_tiers(self.bot, log)
        try:
            merged = shared_config.merge_onboarding_config_early()
        except Exception as exc:  # pragma: no cover - defensive logging
            human_log.human("warn", "Config preload failed", error=repr(exc))
        else:
            log.debug("runtime: onboarding config preload merged %d keys", merged)
        from shared.sheets.cache_scheduler import (
            emit_schedule_log,
            ensure_cache_registration,
            preload_on_startup,
            register_refresh_job,
        )
        from modules.ops import cleanup_watcher, server_map as server_map_module

        ensure_cache_registration()
        await preload_on_startup()
        cache_specs = (
            ("clans", timedelta(hours=3), "3h"),
            ("templates", timedelta(days=7), "7d"),
            ("clan_tags", timedelta(days=7), "7d"),
            ("onboarding_questions", timedelta(days=7), "7d"),
        )
        successes: list[tuple[Any, Any]] = []
        failure: tuple[str, BaseException] | None = None
        for bucket, interval, cadence in cache_specs:
            try:
                spec, job = register_refresh_job(
                    self,
                    bucket=bucket,
                    interval=interval,
                    cadence_label=cadence,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                log.exception("failed to schedule cache refresh", extra={"bucket": bucket})
                if failure is None:
                    failure = (bucket, exc)
                continue
            successes.append((spec, job))

        cleanup_spec_entry: tuple[Any, Any] | None = None
        try:
            cleanup_interval = cleanup_watcher.get_cleanup_interval_hours()
            cleanup_logger = logging.getLogger("c1c.cleanup")
            cleanup_job = self.scheduler.every(
                hours=float(cleanup_interval),
                tag="cleanup",
                name="cleanup_watcher",
            )

            async def cleanup_runner() -> None:
                await cleanup_watcher.run_cleanup(self.bot, cleanup_logger)

            cleanup_job.do(cleanup_runner)
            cleanup_spec_entry = (
                SimpleNamespace(bucket="cleanup", cadence_label=f"{cleanup_interval}h"),
                cleanup_job,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            log.exception("failed to schedule cleanup watcher")
            if failure is None:
                failure = ("cleanup", exc)

        if cleanup_spec_entry is not None:
            successes.append(cleanup_spec_entry)

        self.scheduler.spawn(
            emit_schedule_log(self, successes, failure),
            name="cache_refresh_schedule_log",
        )
        try:
            server_map_module.schedule_server_map_job(self)
        except Exception:  # pragma: no cover - defensive scheduler guard
            log.exception("failed to schedule server map refresh job")
        await self.bot.start(token)

    async def close(self) -> None:
        await self.shutdown_webserver()
        await self.scheduler.shutdown()
        set_active_runtime(None)
