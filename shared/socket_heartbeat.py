from __future__ import annotations

# shared/socket_heartbeat.py
"""
Lightweight gateway heartbeat tracker.

Usage:
    from shared import socket_heartbeat as hb

    # on *every* gateway event (READY, MESSAGE_CREATE, etc.)
    hb.touch()

    # health probes / watchdog
    age = await hb.age_seconds()  # how long since last gateway activity

Design:
- Single in-process tracker (module-level singleton).
- Async-safe; uses an asyncio.Lock so calls from multiple tasks are fine.
- Cheap: only stores a monotonic timestamp.
"""

import asyncio
import time
from typing import Optional


class _Heartbeat:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_monotonic: float = time.monotonic()

    async def _set_now(self) -> None:
        async with self._lock:
            self._last_monotonic = time.monotonic()

    def touch_now(self) -> None:
        """
        Fast, sync variant for hot paths (discord.py event handlers are fine).
        """
        self._last_monotonic = time.monotonic()

    async def age_seconds(self) -> float:
        """
        Returns seconds since the last touch(). Non-blocking read.
        """
        # Read without lock; slight race is fine for health purposes.
        last = self._last_monotonic
        return max(0.0, time.monotonic() - last)

    async def last_timestamp(self) -> float:
        """
        Returns the raw monotonic timestamp of the last activity.
        """
        return self._last_monotonic


# Singleton instance (module-level)
_hb = _Heartbeat()


# Public API

def touch() -> None:
    """
    Record 'now' as the last time we saw any gateway activity.
    Prefer this sync function in event handlers for minimal overhead.
    """
    _hb.touch_now()


async def age_seconds() -> float:
    """
    Seconds since the last gateway activity.
    """
    return await _hb.age_seconds()


async def last_timestamp() -> float:
    """
    Monotonic timestamp of last activity.
    """
    return await _hb.last_timestamp()

