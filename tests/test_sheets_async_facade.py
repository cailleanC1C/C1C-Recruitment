import asyncio
from unittest.mock import patch

from shared.sheets import async_facade as sheets


class _Dummy:
    def __init__(self) -> None:
        self.called = 0

    def fn(self, *args, **kwargs):
        self.called += 1
        return 42


def test_facade_uses_async_adapter(monkeypatch):
    async def runner() -> None:
        dummy = _Dummy()

        with patch("shared.sheets.async_facade._adapter.arun") as mocked_arun:
            async def passthrough(func, *args, **kwargs):
                return func(*args, **kwargs)

            mocked_arun.side_effect = passthrough

            from shared.sheets import recruitment as sync_recruitment

            monkeypatch.setattr(sync_recruitment, "fetch_clans", dummy.fn, raising=True)

            result = await sheets.fetch_clans(force=False)

            assert result == 42
            assert mocked_arun.called
            assert dummy.called == 1

    asyncio.run(runner())

