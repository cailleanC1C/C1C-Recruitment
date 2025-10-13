from __future__ import annotations

# shared/watchdog.py
"""
Watchdog loop mirrored from the battle-tested legacy bots.

Key behaviors:
- Polls the gateway heartbeat age at the configured keepalive cadence.
- If connected but idle for too long ("zombie"), restarts once latency also
  looks bad or is unavailable.
- If disconnected longer than the allowed grace, restarts immediately.

On Render the process exit will trigger a clean restart.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Awaitable, Callable, Optional

from shared.socket_heartbeat import GatewaySnapshot

ProbeFn = Callable[[], Awaitable[float]]
StateProbe = Callable[[], GatewaySnapshot]
LatencyProbe = Callable[[], Optional[float]]

log = logging.getLogger("watchdog")


async def run(
    heartbeat_probe: ProbeFn,
    *,
    stall_after_sec: int = 120,
    check_every: int = 30,
    state_probe: Optional[StateProbe] = None,
    disconnect_grace_sec: Optional[int] = None,
    latency_probe: Optional[LatencyProbe] = None,
) -> None:
    """
    Periodically checks the age of the last gateway event using the
    proven logic from the MM/WC watchdogs.

    Args:
        heartbeat_probe: coroutine returning age since the last event.
        stall_after_sec: treat heartbeat as zombie beyond this age.
        check_every: watchdog loop cadence.
        state_probe: optional snapshot provider for connection state.
        disconnect_grace_sec: grace window before exiting while disconnected.
        latency_probe: optional callable returning gateway latency in seconds.
    """

    disconnect_limit = disconnect_grace_sec or stall_after_sec
    log.info(
        "[watchdog] active: stall_after=%ss, interval=%ss, disconnect_grace=%ss",
        stall_after_sec,
        check_every,
        disconnect_limit,
    )
    last_ok: float = time.monotonic()

    while True:
        try:
            age = await heartbeat_probe()
            snapshot = state_probe() if state_probe else None
            connected = snapshot.connected if snapshot else age <= stall_after_sec
            disconnect_age = snapshot.disconnect_age if snapshot else None

            if connected:
                if age <= stall_after_sec:
                    last_ok = time.monotonic()
                else:
                    latency = None
                    if latency_probe:
                        try:
                            latency = latency_probe()
                        except Exception as exc:
                            log.debug("[watchdog] latency probe failed: %s", exc)

                    since_ok = round(time.monotonic() - last_ok, 1)
                    log_args = {
                        "age": f"{age:.1f}",
                        "stall": stall_after_sec,
                        "since_ok": since_ok,
                        "latency": latency,
                    }
                    if latency is None or latency > 10.0:
                        log.error(
                            "[watchdog] zombie: age=%(age)s>%(stall)s, "
                            "since_ok=%(since_ok)s, latency=%(latency)s — exiting",
                            log_args,
                        )
                        sys.stdout.flush()
                        sys.stderr.flush()
                        os._exit(1)
                    else:
                        log.warning(
                            "[watchdog] heartbeat old but latency healthy "
                            "(age=%(age)s, latency=%(latency)s) — skipping restart",
                            log_args,
                        )
            else:
                down_for = disconnect_age if disconnect_age is not None else age
                if down_for > disconnect_limit:
                    log.error(
                        "[watchdog] disconnected for %.1fs (limit=%ss) — exiting",
                        down_for,
                        disconnect_limit,
                    )
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(1)

        except Exception as exc:
            log.exception("[watchdog] error during probe: %s", exc)

        await asyncio.sleep(check_every)

