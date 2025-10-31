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

        from shared.sheets import core as _sync_core

        def fake_client():
            called["client"] = True
            return object()

        async def fake_open_spreadsheet(_client, _sheet_id, **_kwargs):
            class _Workbook:
                sheet1 = object()

            return _Workbook()

        async def fake_by_title(_workbook, _name, **_kwargs):
            return object()

        async def fake_by_index(_workbook, _index, **_kwargs):
            return object()

        async def fake_values_get(_worksheet, _range, **_kwargs):
            called["n"] += 1
            return {"ok": True}

        async def fake_values_all(_worksheet, **_kwargs):
            called["n"] += 1
            return {"ok": True}

        monkeypatch.setattr(_sync_core, "get_service_account_client", fake_client, raising=True)
        monkeypatch.setattr(
            sheets._adapter, "aopen_spreadsheet", fake_open_spreadsheet, raising=True
        )
        monkeypatch.setattr(
            sheets._adapter, "aworksheet_by_title", fake_by_title, raising=True
        )
        monkeypatch.setattr(
            sheets._adapter, "aworksheet_by_index", fake_by_index, raising=True
        )
        monkeypatch.setattr(
            sheets._adapter, "aworksheet_values_get", fake_values_get, raising=True
        )
        monkeypatch.setattr(
            sheets._adapter, "aworksheet_values_all", fake_values_all, raising=True
        )

        with patch("shared.sheets.async_facade._adapter.arun") as arun:
            async def passthrough(fn, *args, **kwargs):
                return fn(*args, **kwargs)

            arun.side_effect = passthrough
            out = await sheets.sheets_read("Sheet1", "A1:B2")

        assert out == {"ok": True}
        assert arun.called
        assert called["n"] == 1

    asyncio.run(runner())
