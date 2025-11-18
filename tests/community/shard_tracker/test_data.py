from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from types import SimpleNamespace

import pytest

from modules.community.shard_tracker import data as shard_data


def test_get_config_reads_sheet(monkeypatch):
    async def runner():
        store = shard_data.ShardSheetStore()
        monkeypatch.setattr(shard_data, "get_milestones_sheet_id", lambda: "sheet-123")
        monkeypatch.setattr(
            shard_data,
            "runtime_config",
            SimpleNamespace(shard_mercy_tab="ShardTracker", shard_mercy_channel_id=987654321),
        )

        config = await store.get_config()

        assert config.sheet_id == "sheet-123"
        assert config.tab_name == "ShardTracker"
        assert config.channel_id == 987654321

    asyncio.run(runner())


def test_get_config_missing_tab_raises(monkeypatch):
    async def runner():
        store = shard_data.ShardSheetStore()
        monkeypatch.setattr(shard_data, "get_milestones_sheet_id", lambda: "sheet-321")
        monkeypatch.setattr(
            shard_data,
            "runtime_config",
            SimpleNamespace(shard_mercy_tab="", shard_mercy_channel_id=999),
        )

        with pytest.raises(shard_data.ShardTrackerConfigError):
            await store.get_config()

    asyncio.run(runner())


def test_load_record_existing_row(monkeypatch):
    async def runner():
        store = shard_data.ShardSheetStore()
        config = shard_data.ShardTrackerConfig(
            sheet_id="sheet-1", tab_name="ShardTracker", channel_id=123
        )
        store.get_config = AsyncMock(return_value=config)

        header = list(shard_data.EXPECTED_HEADERS)
        row = [
            "12345",
            "Tester",
            "5",
            "6",
            "7",
            "8",
            "10",
            "11",
            "12",
            "13",
            "14",
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            "2024-01-03T00:00:00+00:00",
            "2024-01-04T00:00:00+00:00",
            "2024-01-05T00:00:00+00:00",
            "2024-01-06T00:00:00+00:00",
        ]

        async def fake_values(sheet_id, tab_name, **kwargs):
            return [header, row]

        monkeypatch.setattr(shard_data.async_core, "afetch_values", fake_values)

        record = await store.load_record(12345, "New Name")

        assert record.row_number == 2
        assert record.voids_owned == 6
        assert record.sacreds_since_lego == 12
        assert record.username_snapshot.startswith("New Name")

    asyncio.run(runner())


def test_load_record_appends_when_missing(monkeypatch):
    async def runner():
        store = shard_data.ShardSheetStore()
        config = shard_data.ShardTrackerConfig(
            sheet_id="sheet-1", tab_name="ShardTracker", channel_id=123
        )
        store.get_config = AsyncMock(return_value=config)

        async def fake_values(sheet_id, tab_name, **kwargs):
            return [list(shard_data.EXPECTED_HEADERS)]

        monkeypatch.setattr(shard_data.async_core, "afetch_values", fake_values)

        class DummyWorksheet:
            def __init__(self) -> None:
                self.append_payloads: list[list[str]] = []

            async def append_row(self, row, value_input_option="RAW"):
                self.append_payloads.append(list(row))

        worksheet = DummyWorksheet()

        async def fake_worksheet(sheet_id, tab_name, **kwargs):
            return worksheet

        async def fake_backoff(func, *args, **kwargs):
            return await func(*args, **kwargs)

        monkeypatch.setattr(shard_data.async_core, "aget_worksheet", fake_worksheet)
        monkeypatch.setattr(shard_data.async_core, "acall_with_backoff", fake_backoff)

        record = await store.load_record(99999, "Fresh User")

        assert record.row_number == 2
        assert worksheet.append_payloads, "append_row should be invoked for new records"
        assert worksheet.append_payloads[0][0] == "99999"

    asyncio.run(runner())


def test_load_record_invalid_header(monkeypatch):
    async def runner():
        store = shard_data.ShardSheetStore()
        config = shard_data.ShardTrackerConfig(
            sheet_id="sheet-1", tab_name="ShardTracker", channel_id=123
        )
        store.get_config = AsyncMock(return_value=config)

        async def fake_values(sheet_id, tab_name, **kwargs):
            return [["discord_id", "unexpected"]]

        monkeypatch.setattr(shard_data.async_core, "afetch_values", fake_values)

        with pytest.raises(shard_data.ShardTrackerSheetError):
            await store.load_record(1, "Name")

    asyncio.run(runner())
