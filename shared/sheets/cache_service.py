from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Awaitable, Callable, Dict, Optional

from modules.common import runtime as rt

UTC = dt.timezone.utc


def _errtext(exc: BaseException) -> str:
    s = str(exc).strip()
    return s or getattr(exc, "__class__", type(exc)).__name__


# Type aliases
Loader = Callable[[], Awaitable[Any]]

class CacheBucket:
    __slots__ = (
        "name",
        "ttl_sec",
        "loader",
        "value",
        "last_refresh",
        "refreshing",
        "last_latency_ms",
        "last_result",
        "last_error",
        "last_retries",
        "last_item_count",
        "last_trigger",
        "last_ttl_expired",
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
        self.last_retries: int = 0
        self.last_item_count: Optional[int] = None
        self.last_trigger: Optional[str] = None
        self.last_ttl_expired: Optional[bool] = None

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
        first_err: Optional[str] = None
        retries = 0
        success = False
        new_val: Any = None
        ttl_expired = False
        try:
            age = b.age_sec()
        except Exception:
            age = None
        if b.last_refresh is None:
            ttl_expired = True
        elif isinstance(age, int):
            ttl_expired = age >= b.ttl_sec
        try:
            # run loader with async backoff (single retry on failure)
            try:
                new_val = await b.loader()
                success = True
            except asyncio.CancelledError:
                # Propagate cancellation so shutdown isn't blocked
                result = "cancelled"
                err_text = "cancelled"
                raise
            except Exception as exc:
                retries = 1
                first_err = _errtext(exc)
                err_text = first_err
                b.last_error = first_err
                await asyncio.sleep(300)  # 5 minutes
                try:
                    new_val = await b.loader()
                    success = True
                    result = "retry_ok"
                except asyncio.CancelledError:
                    result = "cancelled"
                    err_text = "cancelled"
                    raise
                except Exception as exc2:
                    second_err = _errtext(exc2)
                    if second_err in (None, "", "-"):
                        err_text = first_err
                    else:
                        err_text = f"{first_err} | retry: {second_err}"
                    result = "fail"
            if success:
                b.value = new_val
                b.last_refresh = dt.datetime.now(UTC)
                b.last_item_count = _count_items(new_val)
        except asyncio.CancelledError:
            # Let the runtime cancel this task; finally will still run
            result = "cancelled"
            err_text = "cancelled"
            raise
        except Exception as e:
            result = "fail"
            err_text = _errtext(e)
        finally:
            b.last_latency_ms = rt.monotonic_ms() - t0
            b.last_result = result
            b.last_error = err_text
            b.last_retries = retries
            b.last_trigger = trigger
            b.last_ttl_expired = ttl_expired
            await self._log_refresh(b, trigger=trigger, actor=actor, retries=retries)
            # clear marker
            b.refreshing = None

    async def _log_refresh(self, b: CacheBucket, *, trigger: str, actor: Optional[str], retries: int) -> None:
        # Format: [refresh] bucket=clans trigger=schedule actor=@user duration=842ms result=ok hits=?,misses=?,retries=1
        error_text = b.last_error or "-"
        if actor == "cron":
            return
        ttl_flag = "unknown"
        if b.last_ttl_expired is True:
            ttl_flag = "true"
        elif b.last_ttl_expired is False:
            ttl_flag = "false"
        count_text = "-"
        if isinstance(b.last_item_count, int):
            count_text = str(b.last_item_count)
        msg = (
            f"[refresh] bucket={b.name} trigger={trigger} "
            f"actor={actor or '-'} duration={b.last_latency_ms or 0}ms "
            f"result={b.last_result or 'unknown'} retries={retries} "
            f"ttl_expired={ttl_flag} count={count_text} error={error_text}"
        )
        try:
            await rt.send_log_message(msg)
        except Exception:
            # Avoid cascading failures if logging channel fails
            pass


def _count_items(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, (set, list, tuple)):
        return len(value)
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        try:
            return len(value)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - defensive guard
            return None
    return None

cache = CacheService()


def capabilities() -> Dict[str, Dict[str, Any]]:
    """Expose cache capabilities for convenience imports."""
    return cache.capabilities()


def get_bucket_snapshot(name: str) -> Dict[str, Any]:
    """Return a read-only snapshot for ``name`` (fail-soft)."""

    try:
        bucket = cache.get_bucket(name)
    except Exception:
        bucket = None

    if bucket is None:
        return {
            "name": name,
            "ttl_sec": None,
            "last_refresh_at": None,
            "next_refresh_at": None,
            "last_result": None,
            "last_error": f"unknown bucket: {name}",
        }

    next_refresh: Optional[dt.datetime]
    try:
        next_refresh = bucket.next_refresh_at()
    except Exception:
        next_refresh = None

    return {
        "name": bucket.name,
        "ttl_sec": getattr(bucket, "ttl_sec", None),
        "last_refresh_at": getattr(bucket, "last_refresh", None),
        "next_refresh_at": next_refresh,
        "last_result": getattr(bucket, "last_result", None),
        "last_error": getattr(bucket, "last_error", None),
        "last_trigger": getattr(bucket, "last_trigger", None),
        "ttl_expired": getattr(bucket, "last_ttl_expired", None),
        "item_count": getattr(bucket, "last_item_count", None),
    }
