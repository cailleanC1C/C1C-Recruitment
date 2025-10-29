"""In-memory event deduplication helpers."""

from __future__ import annotations

import time
from collections import OrderedDict

__all__ = ["EventDeduper"]


class EventDeduper:
    """Deduplicate bursty events over a sliding window."""

    def __init__(self, window_s: float = 5.0, *, max_keys: int = 256) -> None:
        self.window = float(max(window_s, 0.0))
        self.max_keys = max(1, int(max_keys))
        self._seen: "OrderedDict[str, float]" = OrderedDict()

    def _expire(self, now: float) -> None:
        window_start = now - self.window
        to_delete = [key for key, ts in self._seen.items() if ts < window_start]
        for key in to_delete:
            self._seen.pop(key, None)

    def should_emit(self, key: str) -> bool:
        now = time.monotonic()
        self._expire(now)
        ts = self._seen.get(key)
        if ts is not None and now - ts < self.window:
            return False
        self._seen[key] = now
        self._seen.move_to_end(key)
        while len(self._seen) > self.max_keys:
            self._seen.popitem(last=False)
        return True
