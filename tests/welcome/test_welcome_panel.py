import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from modules.onboarding.controllers import welcome_controller as welcome
from modules.onboarding.ui import panels
from modules.onboarding.ui.panels import OnboardWizard


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


def test_panel_button_launch_posts_wizard_message(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", AsyncMock())
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        controller = MagicMock()
        controller.render_step = MagicMock(return_value="Step 1")

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

        async def _defer(*_, **__):
            response.is_done.return_value = True

        response.defer = AsyncMock(side_effect=_defer)
        followup = SimpleNamespace(send=AsyncMock())

        class DummyThread:
            def __init__(self) -> None:
                self.sent = AsyncMock()

            async def send(self, *args: object, **kwargs: object):
                return await self.sent(*args, **kwargs)

        dummy_thread = DummyThread()
        monkeypatch.setattr(panels.discord, "Thread", DummyThread)

        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            edit_original_response=AsyncMock(),
            user=SimpleNamespace(id=5555, roles=[], display_name="Guardian"),
            channel=dummy_thread,
            channel_id=thread_id,
            message=_DummyMessage(id=3333),
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.render_step.assert_called_once_with(thread_id, step=0)
        response.defer.assert_awaited_once()
        dummy_thread.sent.assert_awaited()
        sent_call = dummy_thread.sent.await_args
        assert sent_call.args[0] == controller.render_step.return_value
        assert isinstance(sent_call.kwargs["view"], OnboardWizard)

    asyncio.run(runner())


def test_panel_button_denied_routes_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        logs_mock = AsyncMock()
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels.logs, "send_welcome_log", logs_mock)
        monkeypatch.setattr(panels.rbac, "is_admin_member", lambda actor: False)
        monkeypatch.setattr(panels.rbac, "is_recruiter", lambda actor: False)

        controller = MagicMock()
        controller.render_step = MagicMock(return_value="Step 1")

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
        ensure_mock = AsyncMock()
        monkeypatch.setattr(view, "_ensure_error_notice", ensure_mock)

        response = SimpleNamespace()
        response.is_done = MagicMock(return_value=False)

        async def _defer(*_, **__):
            response.is_done.return_value = True

        response.defer = AsyncMock(side_effect=_defer)
        followup = SimpleNamespace(send=AsyncMock())
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            edit_original_response=AsyncMock(),
            user=SimpleNamespace(id=9999, roles=[], display_name="Member"),
            channel=None,
            channel_id=thread_id,
            message=_DummyMessage(id=2222),
        )

        button = next(child for child in view.children if child.custom_id == panels.OPEN_QUESTIONS_CUSTOM_ID)
        await button.callback(interaction)

        controller.render_step.assert_not_called()
        followup.send.assert_not_awaited()
        response.defer.assert_not_awaited()
        assert ensure_mock.await_count == 1
        assert logs_mock.await_count == 0

    asyncio.run(runner())
