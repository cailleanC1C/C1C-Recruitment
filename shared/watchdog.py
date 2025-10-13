# shared/watchdog.py
"""
Simple watchdog that restarts the container if the gateway heartbeat
goes stale for longer than WATCHDOG_STALL_SEC.

It runs as an asyncio background task:
    asyncio.create_task(watchdog.run(hb.age_seconds, 120))

On Render the process exit will trigger a clean restart.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Awaitable, Callable

ProbeFn = Callable[[], Awaitable[float]]
log = logging.getLogger("watchdog")


async def run(heartbeat_probe: ProbeFn, stall_after_sec: int = 120, check_every: int = 30) -> None:
    """
    Periodically checks the age of the last gateway event.
    If it exceeds stall_after_sec, logs and terminates the process.
    """
    log.info(f"[watchdog] active: stall_after={stall_after_sec}s, interval={check_every}s")
    last_ok: float = time.monotonic()

    while True:
        try:
            age = await heartbeat_probe()
            if age <= stall_after_sec:
                last_ok = time.monotonic()
            else:
                since_ok = round(time.monotonic() - last_ok, 1)
                log.error(
                    f"[watchdog] heartbeat stale ({age:.1f}s > {stall_after_sec}s) "
                    f"no activity for {since_ok}s — exiting"
                )
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(1)
        except Exception as exc:
            log.exception(f"[watchdog] error during probe: {exc}")

        await asyncio.sleep(check_every)

