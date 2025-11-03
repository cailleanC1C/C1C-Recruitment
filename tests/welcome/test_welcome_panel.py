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


def test_panel_button_launch_posts_wizard(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", AsyncMock())
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        thread_id = 7777
        controller = SimpleNamespace()
        question = {"label": "Question", "qid": "qid", "type": "short"}

        async def _load(tid: int) -> None:
            controller.questions_by_thread[tid] = [question]

        controller.get_or_load_questions = AsyncMock(side_effect=_load)
        controller.render_step = MagicMock(return_value="Question text")
        controller.questions_by_thread = {}
        controller.answers_by_thread = {}
        controller.has_answer = MagicMock(return_value=False)
        controller._question_key = lambda q: q.get("qid", "")
        controller._answer_for = MagicMock(return_value=None)

        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        response = SimpleNamespace()
        response.is_done = MagicMock(return_value=False)
        response.send_message = AsyncMock()
        followup = SimpleNamespace(send=AsyncMock())
        app_permissions = SimpleNamespace(
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            read_message_history=True,
        )
        original_message = SimpleNamespace(edit=AsyncMock())
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            edit_original_response=AsyncMock(),
            user=SimpleNamespace(id=5555, roles=[], display_name="Guardian"),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=3333),
            app_permissions=app_permissions,
            original_response=AsyncMock(return_value=original_message),
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.get_or_load_questions.assert_awaited_once_with(thread_id)
        controller.render_step.assert_called_once_with(thread_id, 0)
        response.send_message.assert_awaited()
        args, kwargs = response.send_message.await_args
        assert kwargs["content"] == "Question text"
        assert isinstance(kwargs["view"], panels.OnboardWizard)
        interaction.original_response.assert_awaited_once_with()
        assert kwargs["view"].message is original_message

    asyncio.run(runner())


def test_panel_button_denied_routes_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        logs_mock = AsyncMock()
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", logs_mock)
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        thread_id = 4242
        controller = SimpleNamespace()
        controller.get_or_load_questions = AsyncMock(return_value=None)
        controller.render_step = MagicMock(return_value="Question text")
        controller.questions_by_thread = {thread_id: [{"label": "Question", "qid": "qid", "type": "short"}]}
        controller.answers_by_thread = {}
        controller.has_answer = MagicMock(return_value=False)
        controller._question_key = lambda question: question.get("qid", "")
        controller._answer_for = MagicMock(return_value=None)

        view = panels.OpenQuestionsPanelView(controller=controller, thread_id=thread_id)
        retry_mock = AsyncMock()
        monkeypatch.setattr(view, "_post_retry_start", retry_mock)

        response = SimpleNamespace()
        response.is_done = MagicMock(return_value=True)
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
            original_response=AsyncMock(),
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.get_or_load_questions.assert_not_awaited()
        controller.render_step.assert_not_called()
        response.send_message.assert_not_awaited()
        retry_mock.assert_awaited_once()
        interaction.original_response.assert_not_awaited()

    asyncio.run(runner())
