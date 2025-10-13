from __future__ import annotations
# shared/health.py
"""
Tiny aiohttp health server with /ready and /healthz.
- /ready  : always 200 once the server is up
- /healthz: 200 if heartbeat is fresh, else 503

You must inject a `heartbeat_probe` coroutine that returns "seconds since last
gateway event". Keep it simple so this module stays testable.

Example:
    from shared import health
    site = await health.start_server(
        heartbeat_probe=hb.age_seconds,
        bot_name="C1C-Recruitment",
        env_name="test",
        port=10000,
        stale_after_sec=120,
    )
"""
import json
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Any

from aiohttp import web

ProbeFn = Callable[[], Awaitable[float]]

async def _ready(_: web.Request) -> web.Response:
    return web.Response(text="ok")

def _json(data: Dict[str, Any], status: int = 200) -> web.Response:
    return web.Response(
        status=status,
        text=json.dumps(data, separators=(",", ":")),
        content_type="application/json",
    )

def _build_app(
    heartbeat_probe: ProbeFn,
    bot_name: str,
    env_name: str,
    stale_after_sec: int,
) -> web.Application:
    app = web.Application()

    app.router.add_get("/ready", _ready)

    async def healthz(_: web.Request) -> web.Response:
        age = await heartbeat_probe()
        healthy = age <= stale_after_sec
        payload = {
            "ok": healthy,
            "bot": bot_name,
            "env": env_name,
            "age_seconds": round(age, 3),
            "stale_after_sec": stale_after_sec,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        return _json(payload, status=200 if healthy else 503)

    app.router.add_get("/healthz", healthz)
    return app

async def start_server(
    *,
    heartbeat_probe: ProbeFn,
    bot_name: str,
    env_name: str,
    port: int,
    stale_after_sec: int = 120,
) -> web.TCPSite:
    """
    Creates and starts the aiohttp site. Returns the TCPSite so callers can
    keep a handle (for tests or graceful shutdown).
    """
    app = _build_app(
        heartbeat_probe=heartbeat_probe,
        bot_name=bot_name,
        env_name=env_name,
        stale_after_sec=stale_after_sec,
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    return site
