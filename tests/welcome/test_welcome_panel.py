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
        controller.diag_target_user_id = MagicMock(return_value=5555)
        controller.check_interaction = AsyncMock(return_value=(True, None))

        async def _fake_modal_launch(thread_id: int, interaction, *, context=None):
            await interaction.response.send_modal("sentinel")

        controller._handle_modal_launch = AsyncMock(side_effect=_fake_modal_launch)

        thread_id = 7777
        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        response = SimpleNamespace(
            is_done=MagicMock(return_value=False),
            send_modal=AsyncMock(),
        )
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
            user=SimpleNamespace(id=5555, roles=[]),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=3333),
            app_permissions=app_permissions,
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller._handle_modal_launch.assert_awaited_once()
        response.send_modal.assert_awaited_once()
        assert response.send_modal.await_args.args[0] == "sentinel"

    asyncio.run(runner())


def test_panel_button_launch_allows_ambiguous_target(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        logs_mock = AsyncMock()
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", logs_mock)
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        controller = MagicMock()
        controller.diag_target_user_id = MagicMock(return_value=None)
        controller.check_interaction = AsyncMock(return_value=(True, None))
        controller._handle_modal_launch = AsyncMock()

        thread_id = 4242
        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        response = SimpleNamespace(
            is_done=MagicMock(return_value=False),
            send_modal=AsyncMock(),
            send_message=AsyncMock(),
        )
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
            user=SimpleNamespace(id=9999, roles=[]),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=2222),
            app_permissions=app_permissions,
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.check_interaction.assert_awaited_once()
        controller._handle_modal_launch.assert_awaited_once()
        followup.send.assert_not_awaited()

    asyncio.run(runner())
