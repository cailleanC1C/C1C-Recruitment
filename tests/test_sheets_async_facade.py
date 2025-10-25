import asyncio
from unittest.mock import patch

from shared.sheets import async_facade as sheets


class _Dummy:
    def __init__(self) -> None:
        self.called = 0

    def fn(self, *args, **kwargs):
        self.called += 1
        return 42


def test_facade_uses_to_thread(monkeypatch):
    async def runner() -> None:
        dummy = _Dummy()

        with patch("asyncio.to_thread") as mocked_to_thread:
            async def passthrough(func, *args, **kwargs):
                return func(*args, **kwargs)

            mocked_to_thread.side_effect = passthrough

            from shared.sheets import recruitment as sync_recruitment

            monkeypatch.setattr(sync_recruitment, "fetch_clans", dummy.fn, raising=True)

            result = await sheets.fetch_clans(force=False)

            assert result == 42
            assert mocked_to_thread.called
            assert dummy.called == 1

    asyncio.run(runner())

