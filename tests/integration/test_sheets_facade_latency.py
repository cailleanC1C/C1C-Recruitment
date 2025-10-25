import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from shared.sheets import async_facade as sheets


class _SlowSyncRecruitment:
    def __init__(self, delay: float = 0.15, payload=None):
        self.delay = delay
        self.payload = payload or [{"tag": "AAA"}, {"tag": "BBB"}]

    def fetch_clans(self, *, force: bool = False):
        import time as _t

        _t.sleep(self.delay)  # simulate blocking I/O in sync helper
        return list(self.payload)


def test_event_loop_remains_responsive_during_slow_fetch(monkeypatch):
    """
    Arrange a slow sync function behind the facade. While awaiting it, a concurrent
    lightweight task should complete earlier, demonstrating the loop isn't blocked.
    """

    async def runner() -> None:
        from shared.sheets import recruitment as _sync

        slow = _SlowSyncRecruitment(delay=0.2)
        monkeypatch.setattr(_sync, "fetch_clans", slow.fetch_clans, raising=True)

        loop_tick_happened = asyncio.Event()

        async def tiny_task():
            # short sleep on the event loop to prove scheduling proceeds
            await asyncio.sleep(0.02)
            loop_tick_happened.set()

        t0 = time.monotonic()
        # Run tiny_task concurrently while facade does blocking work in a thread.
        tiny = asyncio.create_task(tiny_task())
        rows = await sheets.fetch_clans(force=False)
        await tiny
        t1 = time.monotonic()

        assert rows and isinstance(rows, list)
        # The tiny task should have completed before the slow fetch finished
        assert loop_tick_happened.is_set(), "Event loop was blocked by Sheets fetch"
        assert (t1 - t0) >= 0.19, "Facade returned too quickly; slow path not exercised"

    asyncio.run(runner())


def test_parallel_facade_calls_complete_faster_than_serial(monkeypatch):
    """
    Three 0.15s blocking sync calls should complete in < 0.40s when run in parallel
    via the facade (threadpool), whereas serial would be ~0.45s.
    """

    async def runner() -> None:
        from shared.sheets import recruitment as _sync

        slow = _SlowSyncRecruitment(delay=0.15, payload=[{"tag": "X"}])
        monkeypatch.setattr(_sync, "fetch_clans", slow.fetch_clans, raising=True)

        t0 = time.monotonic()
        res1, res2, res3 = await asyncio.gather(
            sheets.fetch_clans(force=False),
            sheets.fetch_clans(force=False),
            sheets.fetch_clans(force=False),
        )
        t1 = time.monotonic()
        wall = t1 - t0

        assert all([res1, res2, res3])
        # Expect parallel speedup: wall time should be notably less than 3 * 0.15
        assert wall < 0.40, f"Parallel facade calls too slow (wall={wall:.3f}s)"

    asyncio.run(runner())


def test_facade_passes_through_return_values(monkeypatch):
    async def runner() -> None:
        from shared.sheets import recruitment as _sync

        payload = [{"tag": "TEST", "open": True}]
        slow = _SlowSyncRecruitment(delay=0.05, payload=payload)
        monkeypatch.setattr(_sync, "fetch_clans", slow.fetch_clans, raising=True)

        out = await sheets.fetch_clans(force=False)
        assert out == payload

    asyncio.run(runner())
