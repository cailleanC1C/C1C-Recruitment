from __future__ import annotations

# shared/socket_heartbeat.py
"""
Gateway heartbeat tracker + connection state used by the watchdog and
health endpoints.

Usage:
    from shared import socket_heartbeat as hb

    hb.note_connected()  # on_connect / on_resumed
    hb.note_ready()      # on_ready
    hb.note_disconnected()  # on_disconnect

    # on *every* gateway event (READY, MESSAGE_CREATE, etc.)
    hb.touch()

    # health probes / watchdog
    age = await hb.age_seconds()            # seconds since last event
    snap = hb.snapshot()                    # consistent view for watchdog

Design:
- Single in-process tracker (module-level singleton).
- All mutation helpers are sync for the hot discord.py paths.
- Stores monotonic timestamps to avoid clock skew surprises.
"""

from dataclasses import dataclass
import time
from typing import Optional


@dataclass(frozen=True)
class GatewaySnapshot:
    """Immutable view of the gateway state used by watchdog logic."""

    connected: bool
    last_event_age: float
    last_ready_age: Optional[float]
    disconnect_age: Optional[float]
    last_event_ts: float
    last_ready_ts: Optional[float]
    last_disconnect_ts: Optional[float]


class _Heartbeat:
    def __init__(self) -> None:
        now = time.monotonic()
        self._last_event_ts: float = now
        self._last_ready_ts: Optional[float] = None
        self._last_disconnect_ts: Optional[float] = None
        self._connected: bool = False

    def touch_now(self) -> None:
        """Fast, sync variant for hot paths (discord.py event handlers)."""

        now = time.monotonic()
        self._last_event_ts = now

    def note_connected(self) -> None:
        now = time.monotonic()
        self._connected = True
        self._last_event_ts = now

    def note_ready(self) -> None:
        now = time.monotonic()
        self._connected = True
        self._last_event_ts = now
        self._last_ready_ts = now

    def note_disconnected(self) -> None:
        now = time.monotonic()
        self._connected = False
        self._last_disconnect_ts = now

    def snapshot(self) -> GatewaySnapshot:
        now = time.monotonic()
        last_event_age = max(0.0, now - self._last_event_ts)
        last_ready_age = (
            None if self._last_ready_ts is None else max(0.0, now - self._last_ready_ts)
        )
        disconnect_age = (
            None
            if self._last_disconnect_ts is None
            else max(0.0, now - self._last_disconnect_ts)
        )
        return GatewaySnapshot(
            connected=self._connected,
            last_event_age=last_event_age,
            last_ready_age=last_ready_age,
            disconnect_age=disconnect_age,
            last_event_ts=self._last_event_ts,
            last_ready_ts=self._last_ready_ts,
            last_disconnect_ts=self._last_disconnect_ts,
        )

    async def age_seconds(self) -> float:
        last = self._last_event_ts
        return max(0.0, time.monotonic() - last)

    async def last_timestamp(self) -> float:
        return self._last_event_ts


# Singleton instance (module-level)
_hb = _Heartbeat()


# Public API

def touch() -> None:
    """
    Record "now" as the last time we saw any gateway activity.
    Prefer this sync function in event handlers for minimal overhead.
    """

    _hb.touch_now()


def note_connected() -> None:
    """Flag the gateway as connected (on_connect/on_resumed)."""

    _hb.note_connected()


def note_ready() -> None:
    """Capture the READY event."""

    _hb.note_ready()


def note_disconnected() -> None:
    """Flag the gateway as disconnected (on_disconnect)."""

    _hb.note_disconnected()


def snapshot() -> GatewaySnapshot:
    """Return a cheap, immutable snapshot for watchdog checks."""

    return _hb.snapshot()


async def age_seconds() -> float:
    """Seconds since the last gateway activity."""

    return await _hb.age_seconds()


async def last_timestamp() -> float:
    """Monotonic timestamp of last activity."""

    return await _hb.last_timestamp()

