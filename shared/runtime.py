from __future__ import annotations

"""shared/runtime.py

Runtime helpers that consolidate the background services shared by the bot:

* `start_webserver` exposes keepalive endpoints for Render and monitors.
* `watchdog` wraps the legacy watchdog loop with unified logging/alerts.
* `schedule_at_times` drives cron-like callbacks based on local times.

Each helper accepts a ``notify`` coroutine. When provided the helper will send
human friendly confirmation/error messages (e.g. to the configured
``LOG_CHANNEL_ID``) while also logging to the standard logger. All functions are
safe to call multiple times; they return the created task/site so the caller can
track lifecycle or cancel on shutdown.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, tzinfo
from typing import Awaitable, Callable, Optional, Sequence

from aiohttp import web

from shared import watchdog as watchdog_loop
from shared.socket_heartbeat import GatewaySnapshot


HeartbeatProbe = Callable[[], Awaitable[float]]
StateProbe = Callable[[], GatewaySnapshot]
LatencyProbe = Callable[[], Optional[float]]
UptimeProbe = Callable[[], float]
NotifyFn = Callable[[str], Awaitable[None]]
SchedulerCallback = Callable[[], Awaitable[None]]


log = logging.getLogger("runtime")


async def _safe_notify(notify: Optional[NotifyFn], message: str) -> None:
    if notify is None:
        return
    try:
        await notify(message)
    except Exception as exc:  # pragma: no cover - defensive logging
        log.warning("[runtime] notify failed: %s", exc)


def _latency_safe(latency_probe: Optional[LatencyProbe]) -> Optional[float]:
    if latency_probe is None:
        return None
    try:
        return latency_probe()
    except Exception as exc:  # pragma: no cover - defensive logging
        log.debug("[runtime] latency probe failed: %s", exc)
        return None


async def start_webserver(
    *,
    heartbeat_probe: HeartbeatProbe,
    bot_name: str,
    env_name: str,
    port: int,
    stale_after_sec: int,
    state_probe: Optional[StateProbe] = None,
    latency_probe: Optional[LatencyProbe] = None,
    uptime_probe: Optional[UptimeProbe] = None,
) -> web.TCPSite:
    """Start an aiohttp server exposing ``/``, ``/health``, and ``/healthz``.

    ``/`` and ``/health`` provide lightweight status payloads suitable for
    platform keepalives, while ``/healthz`` returns a strict 200/503 view for
    alerting pipelines.
    """

    async def _health_payload() -> tuple[dict, bool]:
        snapshot = state_probe() if state_probe else None
        last_event_age = snapshot.last_event_age if snapshot else await heartbeat_probe()
        connected = snapshot.connected if snapshot else last_event_age <= stale_after_sec
        disconnect_age = snapshot.disconnect_age if snapshot else None
        latency = _latency_safe(latency_probe)
        uptime = uptime_probe() if uptime_probe else None

        healthy = connected and last_event_age <= stale_after_sec
        if disconnect_age is not None:
            healthy = healthy and disconnect_age <= stale_after_sec

        payload = {
            "ok": healthy,
            "bot": bot_name,
            "env": env_name,
            "age_seconds": round(last_event_age, 3),
            "stale_after_sec": stale_after_sec,
            "connected": connected,
            "disconnect_age": None if disconnect_age is None else round(disconnect_age, 3),
            "latency": latency,
            "uptime_sec": None if uptime is None else round(float(uptime), 3),
            "at": datetime.now(UTC).isoformat(),
        }
        return payload, healthy

    async def _ok(_: web.Request) -> web.Response:
        payload, _ = await _health_payload()
        return web.json_response(payload, status=200)

    async def _health(_: web.Request) -> web.Response:
        payload, healthy = await _health_payload()
        return web.json_response(payload, status=200 if healthy else 206)

    async def _healthz(_: web.Request) -> web.Response:
        payload, healthy = await _health_payload()
        return web.json_response(payload, status=200 if healthy else 503)

    app = web.Application()
    app.router.add_get("/", _ok)
    app.router.add_get("/health", _health)
    app.router.add_get("/healthz", _healthz)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("[runtime] web server listening on :%s", port)
    return site


def watchdog(
    *,
    heartbeat_probe: HeartbeatProbe,
    check_sec: int,
    stall_sec: int,
    disconnect_grace: int,
    state_probe: Optional[StateProbe] = None,
    latency_probe: Optional[LatencyProbe] = None,
    start_delay: float = 0.0,
    notify: Optional[NotifyFn] = None,
    label: str = "Watchdog",
) -> asyncio.Task:
    """Start the watchdog loop as a managed ``asyncio.Task``."""

    loop = asyncio.get_running_loop()

    async def _runner() -> None:
        if start_delay:
            await asyncio.sleep(start_delay)
        await _safe_notify(
            notify,
            f"✅ {label} armed — stall={stall_sec}s, check={check_sec}s, disconnect_grace={disconnect_grace}s",
        )
        try:
            await watchdog_loop.run(
                heartbeat_probe,
                stall_after_sec=stall_sec,
                check_every=check_sec,
                state_probe=state_probe,
                disconnect_grace_sec=disconnect_grace,
                latency_probe=latency_probe,
            )
        except asyncio.CancelledError:
            await _safe_notify(notify, f"⚠️ {label} cancelled")
            raise
        except Exception as exc:
            log.exception("[runtime] %s crashed: %s", label, exc)
            await _safe_notify(notify, f"❌ {label} crashed: {exc!r}")
            raise

    return loop.create_task(_runner(), name=f"runtime:{label.lower().replace(' ', '-')}")


@dataclass(frozen=True)
class _ScheduleConfig:
    times: Sequence[time]
    timezone: tzinfo


def _parse_times(times_csv: str) -> Sequence[time]:
    slots: list[time] = []
    for part in times_csv.split(","):
        trimmed = part.strip()
        if not trimmed:
            continue
        try:
            hour_str, minute_str = trimmed.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
            slots.append(time(hour=hour, minute=minute, tzinfo=None))
        except Exception as exc:
            raise ValueError(f"Invalid time entry {trimmed!r}") from exc
    if not slots:
        raise ValueError("No valid refresh times provided")
    return sorted(slots)


def _load_schedule_config(times_csv: str, timezone_name: str) -> _ScheduleConfig:
    try:
        from zoneinfo import ZoneInfo
    except Exception as exc:  # pragma: no cover - Python <3.9 fallback
        raise RuntimeError("zoneinfo module unavailable") from exc

    tz: tzinfo
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        log.warning("[runtime] unknown timezone %s — defaulting to UTC", timezone_name)
        tz = UTC

    times = _parse_times(times_csv)
    return _ScheduleConfig(times=times, timezone=tz)


def _next_occurrence(cfg: _ScheduleConfig, *, now: datetime) -> datetime:
    today = now.date()
    candidates: list[datetime] = []
    for slot in cfg.times:
        candidate = datetime.combine(today, slot, tzinfo=cfg.timezone)
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def schedule_at_times(
    *,
    times_csv: str,
    timezone_name: str,
    callback: SchedulerCallback,
    notify: Optional[NotifyFn] = None,
    label: str = "Scheduled refresh",
) -> asyncio.Task:
    """Run ``callback`` at each configured local time (HH:MM) indefinitely."""

    loop = asyncio.get_running_loop()
    cfg = _load_schedule_config(times_csv, timezone_name)

    async def _runner() -> None:
        await _safe_notify(
            notify,
            f"✅ {label} armed — times={','.join(t.strftime('%H:%M') for t in cfg.times)} ({timezone_name})",
        )
        while True:
            now = datetime.now(cfg.timezone)
            target = _next_occurrence(cfg, now=now)
            wait_seconds = max(0.0, (target - now).total_seconds())
            log.debug("[runtime] %s sleeping %.1fs until %s", label, wait_seconds, target)
            try:
                await asyncio.sleep(wait_seconds)
                await callback()
                await _safe_notify(
                    notify,
                    f"✅ {label} completed at {datetime.now(cfg.timezone).isoformat(timespec='minutes')}",
                )
            except asyncio.CancelledError:
                await _safe_notify(notify, f"⚠️ {label} cancelled")
                raise
            except Exception as exc:
                log.exception("[runtime] %s failed: %s", label, exc)
                await _safe_notify(notify, f"❌ {label} failed: {exc!r}")

    return loop.create_task(_runner(), name=f"runtime:{label.lower().replace(' ', '-')}")
