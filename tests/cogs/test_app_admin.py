import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.app_admin import AppAdmin
from modules.ops import server_map


def test_servermap_refresh_command_respects_feature_toggle(monkeypatch):
    async def _run() -> None:
        bot = object()
        cog = AppAdmin(bot)
        ctx = SimpleNamespace()
        ctx.reply = AsyncMock()

        monkeypatch.setattr(server_map.feature_flags, "is_enabled", lambda key: False)

        async def _fail(*_args, **_kwargs):  # pragma: no cover - defensive assertion
            raise AssertionError("refresh_server_map should not be invoked when disabled")

        monkeypatch.setattr(server_map, "refresh_server_map", _fail)

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        from modules.common import runtime as runtime_helpers

        monkeypatch.setattr(runtime_helpers, "send_log_message", fake_log)

        await cog.servermap_refresh.callback(cog, ctx)

        ctx.reply.assert_awaited_once_with(
            "Server map feature is currently disabled in FeatureToggles.",
            mention_author=False,
        )
        assert log_messages == ["📘 Server map — skipped • reason=feature_disabled"]

    asyncio.run(_run())


def test_servermap_refresh_command_invokes_refresh_when_enabled(monkeypatch):
    async def _run() -> None:
        bot = object()
        cog = AppAdmin(bot)
        ctx = SimpleNamespace()
        ctx.reply = AsyncMock()

        monkeypatch.setattr(server_map.feature_flags, "is_enabled", lambda key: True)

        refresh = AsyncMock(
            return_value=server_map.ServerMapResult(status="ok", message_count=2, total_chars=1200)
        )
        monkeypatch.setattr(server_map, "refresh_server_map", refresh)

        await cog.servermap_refresh.callback(cog, ctx)

        refresh.assert_awaited_once()
        ctx.reply.assert_awaited_once_with(
            "Server map refreshed — messages=2 • chars=1200.",
            mention_author=False,
        )

    asyncio.run(_run())
