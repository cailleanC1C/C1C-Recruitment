import asyncio
from unittest.mock import AsyncMock

from modules.ops import server_map


def test_refresh_server_map_skips_when_feature_disabled(monkeypatch):
    async def _run() -> None:
        bot = AsyncMock()
        bot.wait_until_ready = AsyncMock()

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        monkeypatch.setattr(server_map.feature_flags, "is_enabled", lambda key: False)

        def _should_not_call() -> None:  # pragma: no cover - defensive assertion
            raise AssertionError("server map config should not be read when disabled")

        monkeypatch.setattr(server_map, "get_server_map_channel_id", _should_not_call)
        monkeypatch.setattr(server_map, "get_server_map_refresh_days", _should_not_call)
        monkeypatch.setattr(server_map.runtime_helpers, "send_log_message", fake_log)

        result = await server_map.refresh_server_map(bot, force=True, actor="scheduler")

        assert result.status == "disabled"
        assert result.reason == "feature_disabled"
        assert log_messages == ["📘 Server map — skipped • reason=feature_disabled"]
        bot.wait_until_ready.assert_awaited()

    asyncio.run(_run())


def test_refresh_server_map_requires_channel_when_enabled(monkeypatch):
    async def _run() -> None:
        bot = AsyncMock()
        bot.wait_until_ready = AsyncMock()

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        monkeypatch.setattr(server_map.feature_flags, "is_enabled", lambda key: True)
        monkeypatch.setattr(server_map, "get_server_map_channel_id", lambda: None)
        monkeypatch.setattr(server_map.runtime_helpers, "send_log_message", fake_log)

        result = await server_map.refresh_server_map(bot, force=True, actor="scheduler")

        assert result.status == "error"
        assert result.reason == "missing_channel_id"
        assert log_messages == ["❌ Server map — error • reason=missing_channel_id"]
        bot.wait_until_ready.assert_awaited()

    asyncio.run(_run())
