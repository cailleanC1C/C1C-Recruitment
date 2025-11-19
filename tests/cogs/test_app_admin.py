import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.app_admin import AppAdmin
from modules.common import feature_flags
from modules.ops import cluster_role_map, server_map
from shared.sheets import recruitment as recruitment_sheet


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


def test_whoweare_command_respects_feature_toggle(monkeypatch):
    async def _run() -> None:
        bot = object()
        cog = AppAdmin(bot)
        ctx = SimpleNamespace()
        ctx.guild = SimpleNamespace(name="Guild")
        ctx.reply = AsyncMock()

        monkeypatch.setattr(feature_flags, "is_enabled", lambda key: False)

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        from modules.common import runtime as runtime_helpers

        monkeypatch.setattr(runtime_helpers, "send_log_message", fake_log)

        await cog.whoweare.callback(cog, ctx)

        ctx.reply.assert_awaited_once_with(
            "Cluster role map feature is disabled in FeatureToggles.",
            mention_author=False,
        )
        assert log_messages == [
            "📘 **Cluster role map** — cmd=whoweare • guild=Guild • status=disabled"
        ]

    asyncio.run(_run())


def test_whoweare_command_reports_sheet_errors(monkeypatch):
    async def _run() -> None:
        bot = object()
        cog = AppAdmin(bot)
        ctx = SimpleNamespace()
        ctx.guild = SimpleNamespace(name="Guild")
        ctx.reply = AsyncMock()

        monkeypatch.setattr(feature_flags, "is_enabled", lambda key: True)
        monkeypatch.setattr(recruitment_sheet, "get_role_map_tab_name", lambda: "WhoWeAre")

        async def raise_error(*_args, **_kwargs):
            raise cluster_role_map.RoleMapLoadError("sheet offline")

        monkeypatch.setattr(cluster_role_map, "fetch_role_map_rows", raise_error)

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        from modules.common import runtime as runtime_helpers

        monkeypatch.setattr(runtime_helpers, "send_log_message", fake_log)

        await cog.whoweare.callback(cog, ctx)

        ctx.reply.assert_awaited_once_with(
            "I couldn’t read the role map sheet (`WhoWeAre`). Please check Config and try again.",
            mention_author=False,
        )
        assert log_messages == [
            "📘 **Cluster role map** — cmd=whoweare • guild=Guild • status=error • reason=sheet offline"
        ]

    asyncio.run(_run())


def test_whoweare_command_posts_rendered_map(monkeypatch):
    async def _run() -> None:
        bot = object()
        cog = AppAdmin(bot)
        ctx = SimpleNamespace()
        ctx.guild = SimpleNamespace(name="Guild")
        ctx.reply = AsyncMock()

        monkeypatch.setattr(feature_flags, "is_enabled", lambda key: True)
        monkeypatch.setattr(recruitment_sheet, "get_role_map_tab_name", lambda: "WhoWeAre")

        async def fake_fetch(*_args, **_kwargs):
            return [cluster_role_map.RoleMapRow("Category", 1, "Name", "desc")]

        monkeypatch.setattr(cluster_role_map, "fetch_role_map_rows", fake_fetch)

        render = cluster_role_map.RoleMapRender(
            message="payload",
            category_count=1,
            role_count=1,
            unassigned_roles=1,
        )

        monkeypatch.setattr(cluster_role_map, "build_role_map_render", lambda guild, entries: render)

        log_messages: list[str] = []

        async def fake_log(message: str) -> None:
            log_messages.append(message)

        from modules.common import runtime as runtime_helpers

        monkeypatch.setattr(runtime_helpers, "send_log_message", fake_log)

        await cog.whoweare.callback(cog, ctx)

        ctx.reply.assert_awaited_once_with("payload", mention_author=False)
        assert log_messages == [
            "📘 **Cluster role map** — cmd=whoweare • guild=Guild • categories=1 • roles=1 "
            "• unassigned_roles=1"
        ]

    asyncio.run(_run())
