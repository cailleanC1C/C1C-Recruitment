from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Awaitable, Callable, Dict, Optional

from .. import runtime as rt

UTC = dt.timezone.utc

# Type aliases
Loader = Callable[[], Awaitable[Any]]

class CacheBucket:
    __slots__ = (
        "name", "ttl_sec", "loader", "value", "last_refresh",
        "refreshing", "last_latency_ms", "last_result", "last_error",
    )
    def __init__(self, name: str, ttl_sec: int, loader: Loader):
        self.name = name
        self.ttl_sec = ttl_sec
        self.loader = loader
        self.value: Any = None
        self.last_refresh: Optional[dt.datetime] = None
        self.refreshing: Optional[asyncio.Task] = None
        self.last_latency_ms: Optional[int] = None
        self.last_result: Optional[str] = None
        self.last_error: Optional[str] = None

    def age_sec(self) -> Optional[int]:
        if not self.last_refresh:
            return None
        return int((dt.datetime.now(UTC) - self.last_refresh).total_seconds())

    def next_refresh_at(self, schedule_hint: Optional[dt.datetime] = None) -> Optional[dt.datetime]:
        if self.last_refresh:
            return self.last_refresh + dt.timedelta(seconds=self.ttl_sec)
        return schedule_hint

class CacheService:
    def __init__(self):
        self._buckets: Dict[str, CacheBucket] = {}

    def register(self, name: str, ttl_sec: int, loader: Loader) -> CacheBucket:
        b = CacheBucket(name, ttl_sec, loader)
        self._buckets[name] = b
        return b

    def get_bucket(self, name: str) -> Optional[CacheBucket]:
        return self._buckets.get(name)

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for name, b in self._buckets.items():
            out[name] = {
                "ttl_sec": b.ttl_sec,
                "last_refresh_at": b.last_refresh,
                "next_refresh_at": b.next_refresh_at(),
                "refresh": lambda n=name: self.refresh_now(n),
            }
        return out

    async def get(self, name: str) -> Any:
        b = self._buckets[name]
        # Fast-path: fresh enough
        age = b.age_sec()
        if age is not None and age < b.ttl_sec and b.value is not None:
            return b.value
        # Otherwise trigger background refresh (debounced) and return stale ASAP
        await self._ensure_background_refresh(name)
        return b.value

    async def invalidate(self, name: str) -> None:
        b = self._buckets[name]
        b.last_refresh = None  # mark stale

    async def refresh_now(
        self, name: str, *, actor: Optional[str] = None, trigger: str = "manual"
    ) -> None:
        await self._refresh(name, trigger=trigger, actor=actor)

    async def _ensure_background_refresh(self, name: str) -> None:
        b = self._buckets[name]
        if b.refreshing and not b.refreshing.done():
            return
        b.refreshing = asyncio.create_task(self._refresh(name, trigger="schedule", actor=None))

    async def _refresh(self, name: str, *, trigger: str, actor: Optional[str]) -> None:
        b = self._buckets[name]
        t0 = rt.monotonic_ms()
        result = "ok"
        err_text: Optional[str] = None
        retries = 0
        try:
            # run loader with async backoff (single retry on failure)
            try:
                new_val = await b.loader()
            except asyncio.CancelledError:
                # Propagate cancellation so shutdown isn't blocked
                result = "cancelled"
                err_text = "cancelled"
                raise
            except Exception:
                retries = 1
                await asyncio.sleep(300)  # 5 minutes
                new_val = await b.loader()
                result = "retry_ok"
            b.value = new_val
            b.last_refresh = dt.datetime.now(UTC)
        except asyncio.CancelledError:
            # Let the runtime cancel this task; finally will still run
            result = "cancelled"
            err_text = "cancelled"
            raise
        except Exception as e:
            result = "fail"
            err_text = str(e)[:200]
        finally:
            b.last_latency_ms = rt.monotonic_ms() - t0
            b.last_result = result
            b.last_error = err_text
            await self._log_refresh(b, trigger=trigger, actor=actor, retries=retries)
            # clear marker
            b.refreshing = None

    async def _log_refresh(self, b: CacheBucket, *, trigger: str, actor: Optional[str], retries: int) -> None:
        # Format: [refresh] bucket=clans trigger=schedule actor=@user duration=842ms result=ok hits=?,misses=?,retries=1
        error_text = b.last_error or "-"
        msg = (
            f"[refresh] bucket={b.name} trigger={trigger} "
            f"actor={actor or '-'} duration={b.last_latency_ms or 0}ms "
            f"result={b.last_result or 'unknown'} retries={retries} "
            f"error={error_text}"
        )
        try:
            await rt.send_log_message(msg)
        except Exception:
            # Avoid cascading failures if logging channel fails
            pass

cache = CacheService()


def capabilities() -> Dict[str, Dict[str, Any]]:
    """Expose cache capabilities for convenience imports."""
    return cache.capabilities()
