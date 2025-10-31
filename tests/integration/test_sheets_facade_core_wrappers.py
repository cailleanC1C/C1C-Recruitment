import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from shared.sheets import async_facade as sheets


def test_core_read_wrapper_uses_async_adapter(monkeypatch):
    # Skip if wrapper not present (keep test non-brittle across modules)
    if not hasattr(sheets, "sheets_read"):
        pytest.skip("sheets_read wrapper not exported")

    async def runner() -> None:
        called = {"n": 0}

        def fake_read(*args, **kwargs):
            called["n"] += 1
            return {"ok": True}

        from shared.sheets import core as _sync_core

        monkeypatch.setattr(_sync_core, "sheets_read", fake_read, raising=True)

        with patch("shared.sheets.async_facade._adapter.arun") as arun:
            async def passthrough(fn, *args, **kwargs):
                return fn(*args, **kwargs)

            arun.side_effect = passthrough
            out = await sheets.sheets_read("Sheet1", "A1:B2")

        assert out == {"ok": True}
        assert arun.called
        assert called["n"] == 1

    asyncio.run(runner())
