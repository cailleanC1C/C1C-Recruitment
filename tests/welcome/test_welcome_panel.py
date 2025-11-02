import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.onboarding.controllers import welcome_controller as welcome
from modules.onboarding.ui import panels


class _DummyMessage(SimpleNamespace):
    pass


def test_locate_welcome_message_skips_thread_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        message = _DummyMessage(id=9001, content="hello")
        fetch_mock = AsyncMock(side_effect=AssertionError("fetch should not be called"))

        class DummyThread:
            def __init__(self) -> None:
                self.id = 1234
                self.starter_message = None
                self.fetch_message = fetch_mock
                self.parent = None

            def history(self, **_: object):  # pragma: no cover - signature shim
                async def _iter():
                    yield message

                return _iter()

        thread = DummyThread()

        result = await welcome.locate_welcome_message(thread)

        assert result is message
        fetch_mock.assert_not_awaited()

    asyncio.run(runner())


def test_panel_button_launch_sends_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", AsyncMock())
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        controller = MagicMock()
        controller.build_modal_stub = MagicMock(return_value="sentinel")

        thread_id = 7777
        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        response = SimpleNamespace()
        response.is_done = MagicMock(return_value=False)

        async def _defer(*_, **__):
            response.is_done.return_value = True

        response.defer = AsyncMock(side_effect=_defer)
        response.send_modal = AsyncMock()
        followup = SimpleNamespace(send=AsyncMock())
        app_permissions = SimpleNamespace(
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            read_message_history=True,
        )
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            edit_original_response=AsyncMock(),
            user=SimpleNamespace(id=5555, roles=[], display_name="Guardian"),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=3333),
            app_permissions=app_permissions,
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.build_modal_stub.assert_called_once_with(thread_id)
        response.defer.assert_not_awaited()
        response.send_modal.assert_awaited_once_with("sentinel")

    asyncio.run(runner())


def test_panel_button_denied_routes_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        logs_mock = AsyncMock()
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", logs_mock)
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        controller = MagicMock()
        controller.build_modal_stub = MagicMock(return_value="sentinel")

        thread_id = 4242
        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        response = SimpleNamespace()
        response.is_done = MagicMock(return_value=False)

        async def _defer(*_, **__):
            response.is_done.return_value = True

        response.defer = AsyncMock(side_effect=_defer)
        response.send_modal = AsyncMock()
        response.send_message = AsyncMock()
        followup = SimpleNamespace(send=AsyncMock())
        app_permissions = SimpleNamespace(
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            read_message_history=True,
        )
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            edit_original_response=AsyncMock(),
            user=SimpleNamespace(id=9999, roles=[], display_name="Member"),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=2222),
            app_permissions=app_permissions,
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.build_modal_stub.assert_called_once_with(thread_id)
        followup.send.assert_not_awaited()
        response.defer.assert_not_awaited()
        assert logs_mock.await_count == 0

    asyncio.run(runner())
