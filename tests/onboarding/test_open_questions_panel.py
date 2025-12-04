import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.onboarding.ui import panels
from modules.onboarding.ui.panels import OpenQuestionsPanelView
from shared.sheets import onboarding_questions


def test_open_questions_button_has_custom_id() -> None:
    async def runner() -> None:
        view = OpenQuestionsPanelView()
        button_ids = [
            getattr(child, "custom_id", None)
            for child in view.children
            if hasattr(child, "custom_id")
        ]

        assert OpenQuestionsPanelView.CUSTOM_ID in button_ids
        assert view.timeout is None

    asyncio.run(runner())


def test_launch_bootstraps_controller_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        panels._CONTROLLERS.clear()

        thread_id = 6543

        class FakeThread:
            def __init__(self, identifier: int) -> None:
                self.id = identifier
                self.parent = None
                self.guild = None
                self.send = AsyncMock(return_value=SimpleNamespace(id=321, channel=self))

        monkeypatch.setattr(panels.discord, "Thread", FakeThread)
        thread = FakeThread(thread_id)

        controller = SimpleNamespace()
        controller.questions_by_thread = {thread_id: ("qid",)}
        controller.get_or_load_questions = AsyncMock(return_value=("qid",))
        controller.render_step = lambda tid, step: "Step 1" if tid == thread_id else ""
        controller.wait_until_ready = AsyncMock(return_value=True)

        async def fake_start(
            thread_obj: FakeThread,
            initiator: object,
            source: str,
            *,
            bot: object | None = None,
            panel_message_id: int | None = None,
            panel_message: object | None = None,
        ) -> None:
            assert source == "panel_button"
            assert thread_obj is thread
            panels.bind_controller(thread_id, controller)

        start_mock = AsyncMock(side_effect=fake_start)
        monkeypatch.setattr(
            "modules.onboarding.welcome_flow.start_welcome_dialog",
            start_mock,
        )

        class DummyResponse:
            def __init__(self) -> None:
                self.deferred = False

            def is_done(self) -> bool:
                return self.deferred

            async def defer(self) -> None:
                self.deferred = True

        response = DummyResponse()
        message = SimpleNamespace(id=111, edit=AsyncMock())
        interaction = SimpleNamespace(
            response=response,
            channel=thread,
            user=SimpleNamespace(id=999, display_name="Recruit"),
            message=message,
            id=2024,
            client=SimpleNamespace(),
        )

        view = OpenQuestionsPanelView()

        button = next(
            child
            for child in view.children
            if getattr(child, "custom_id", None) == OpenQuestionsPanelView.CUSTOM_ID
        )

        await button.callback(interaction)

        start_mock.assert_awaited_once()
        controller.get_or_load_questions.assert_awaited_once()
        controller.wait_until_ready.assert_awaited_once()
        thread.send.assert_awaited()

        panels._CONTROLLERS.pop(thread_id, None)

    asyncio.run(runner())


def test_resume_button_visible_when_session_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panels.OpenQuestionsPanelView, "_session_exists", staticmethod(lambda _thread_id, _user_id: True))

    async def runner() -> None:
        view = OpenQuestionsPanelView(thread_id=1234, target_user_id=5678)
        resume_ids = [
            getattr(child, "custom_id", None)
            for child in view.children
            if hasattr(child, "custom_id")
        ]
        assert "welcome.panel.resume" in resume_ids

    asyncio.run(runner())


def test_restart_from_view_responds_before_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)

        class DummyResponse:
            def __init__(self) -> None:
                self.sent_messages: list[str] = []
                self.deferred = False

            def is_done(self) -> bool:
                return bool(self.sent_messages) or self.deferred

            async def send_message(self, message: str, *, ephemeral: bool = False) -> None:
                if self.is_done():
                    raise AssertionError("response already sent")
                self.sent_messages.append(message)

            async def defer(self, ephemeral: bool = False) -> None:
                if self.is_done():
                    raise AssertionError("response already sent")
                self.deferred = True

        response = DummyResponse()

        async def fake_log(level: str, **payload: object) -> None:
            assert response.is_done()

        async def fake_lifecycle(**payload: object) -> None:
            assert response.is_done()

        log_mock = AsyncMock(side_effect=fake_log)
        lifecycle_mock = AsyncMock(side_effect=fake_lifecycle)
        monkeypatch.setattr(panels.logs, "send_welcome_log", log_mock)
        monkeypatch.setattr(panels.logs, "log_onboarding_panel_lifecycle", lifecycle_mock)

        view = OpenQuestionsPanelView()
        interaction = SimpleNamespace(
            response=response,
            channel=None,
            message=SimpleNamespace(id=1234),
            user=SimpleNamespace(id=5678, display_name="Recruit"),
            followup=None,
        )

        await view._restart_from_view(interaction, {"view": "panel"})

        assert response.is_done()
        assert response.deferred is True
        assert not response.sent_messages
        assert log_mock.await_count + lifecycle_mock.await_count >= 1

    asyncio.run(runner())


def test_status_row_visible_for_text_inputs() -> None:
    async def runner() -> None:
        thread_id = 101
        question = SimpleNamespace(
            qid="ign",
            label="IGN",
            type="short",
            options=[],
            required=True,
        )

        class DummyController:
            def __init__(self) -> None:
                self.questions_by_thread = {thread_id: [question]}
                self.answers_by_thread = {thread_id: {}}

            def render_step(self, tid: int, step: int) -> str:
                assert tid == thread_id
                assert step == 0
                return "**Prompt**"

            def has_answer(self, tid: int, _question: object) -> bool:
                return bool(self.answers_by_thread.get(tid))

            def _question_key(self, q: object) -> str:
                return getattr(q, "qid", "")

            def _answer_for(self, tid: int, key: str) -> object | None:
                return self.answers_by_thread.get(tid, {}).get(key)

            def _visibility_map(self, _tid: int) -> dict[str, dict[str, str]]:
                return {}

            def build_panel_content(self, tid: int, step: int) -> str:
                base = self.render_step(tid, step)

                questions = self.questions_by_thread.get(tid, [])
                question = questions[step] if 0 <= step < len(questions) else None

                if not question:
                    return base

                q_type = getattr(question, "type", "")
                is_text_input = q_type in ("short", "long")

                if is_text_input and not self.has_answer(tid, question):
                    return f"{base}\n\nWaiting for your reply."

                return base

        class DummyMessage:
            def __init__(self) -> None:
                self.last_edit: SimpleNamespace | None = None

            async def edit(self, *, content=None, view=None):
                self.last_edit = SimpleNamespace(content=content, view=view)
                return self

        controller = DummyController()
        wizard = panels.OnboardWizard(controller, thread_id, step=0)
        message = DummyMessage()
        wizard.attach(message)  # type: ignore[arg-type]

        await wizard.refresh()

        assert message.last_edit is not None
        assert "Waiting for your reply." in message.last_edit.content

    asyncio.run(runner())


def test_status_row_hidden_for_select_and_bool() -> None:
    async def runner() -> None:
        thread_id = 202
        select_question = SimpleNamespace(
            qid="clan",
            label="Clan",
            type="single-select",
            options=[SimpleNamespace(label="Yes", value="yes")],
            required=True,
        )
        bool_question = SimpleNamespace(
            qid="ready",
            label="Ready?",
            type="bool",
            options=[],
            required=True,
        )

        class DummyController:
            def __init__(self) -> None:
                self.questions_by_thread = {thread_id: [select_question]}
                self.answers_by_thread = {thread_id: {}}

            def render_step(self, tid: int, step: int) -> str:
                return "**Select Prompt**"

            def has_answer(self, tid: int, _question: object) -> bool:
                return False

            def _question_key(self, q: object) -> str:
                return getattr(q, "qid", "")

            def _answer_for(self, tid: int, key: str) -> object | None:
                return self.answers_by_thread.get(tid, {}).get(key)

            def _visibility_map(self, _tid: int) -> dict[str, dict[str, str]]:
                return {}

            def build_panel_content(self, tid: int, step: int) -> str:
                base = self.render_step(tid, step)

                questions = self.questions_by_thread.get(tid, [])
                question = questions[step] if 0 <= step < len(questions) else None

                if not question:
                    return base

                q_type = getattr(question, "type", "")
                is_text_input = q_type in ("short", "long")

                if is_text_input and not self.has_answer(tid, question):
                    return f"{base}\n\nWaiting for your reply."

                return base

        class DummyMessage:
            def __init__(self) -> None:
                self.last_edit: SimpleNamespace | None = None

            async def edit(self, *, content=None, view=None):
                self.last_edit = SimpleNamespace(content=content, view=view)
                return self

        controller = DummyController()
        wizard = panels.OnboardWizard(controller, thread_id, step=0)
        message = DummyMessage()
        wizard.attach(message)  # type: ignore[arg-type]

        await wizard.refresh()
        assert message.last_edit is not None
        assert "Waiting for your reply." not in message.last_edit.content

        # Swap to bool question and ensure status stays hidden
        controller.questions_by_thread[thread_id] = [bool_question]
        await wizard.refresh()
        assert message.last_edit is not None
        assert "Waiting for your reply." not in message.last_edit.content

    asyncio.run(runner())


def test_launch_uses_cached_questions_only(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        network_guard = AsyncMock(side_effect=AssertionError("network not allowed"))
        monkeypatch.setattr(onboarding_questions, "fetch_question_rows_async", network_guard)
        monkeypatch.setattr(panels, "OnboardWizard", lambda **_: SimpleNamespace())

        send_exception = AsyncMock()
        monkeypatch.setattr(panels.logs, "send_welcome_exception", send_exception)

        thread_id = 4321
        class FakeThread:
            def __init__(self, identifier: int) -> None:
                self.id = identifier
                self.parent = None
                self.guild = None
                self.send = AsyncMock()

        monkeypatch.setattr(panels.discord, "Thread", FakeThread)
        thread = FakeThread(thread_id)

        controller = SimpleNamespace()
        controller.questions_by_thread = {thread_id: ("qid",)}
        controller.prompt_retry = AsyncMock()
        controller.get_or_load_questions = AsyncMock(return_value=("qid",))
        controller.render_step = lambda tid, step: f"Step {step + 1}" if tid == thread_id else ""

        class DummyResponse:
            def __init__(self) -> None:
                self.deferred = False

            def is_done(self) -> bool:
                return self.deferred

            async def defer(self, thinking: bool = True) -> None:
                self.deferred = True

            async def edit_message(self, *, view: object | None = None) -> None:
                self.deferred = True

        response = DummyResponse()
        message = SimpleNamespace(id=1, edit=AsyncMock())
        interaction = SimpleNamespace(
            response=response,
            channel=thread,
            user=SimpleNamespace(id=99, display_name="Recruit"),
            message=message,
            id=777,
        )

        view = OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        button = next(
            child
            for child in view.children
            if getattr(child, "custom_id", None) == OpenQuestionsPanelView.CUSTOM_ID
        )

        await button.callback(interaction)

        controller.get_or_load_questions.assert_awaited_once()
        thread.send.assert_not_awaited()
        assert response.deferred is True
        network_guard.assert_not_awaited()
        send_exception.assert_not_awaited()
        interaction.message.edit.assert_awaited_once()

    asyncio.run(runner())


def test_launch_empty_cache_logs_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)
        monkeypatch.setattr(panels, "OnboardWizard", lambda **_: SimpleNamespace())

        error_message = "onboarding_questions cache is empty (should be preloaded)"
        controller = SimpleNamespace()
        controller.questions_by_thread = {}
        controller.prompt_retry = AsyncMock()
        controller.get_or_load_questions = AsyncMock(side_effect=RuntimeError(error_message))
        controller.render_step = lambda _tid, _step: ""

        class DummyResponse:
            def __init__(self) -> None:
                self.deferred = False
                self.sent_messages: list[str] = []

            def is_done(self) -> bool:
                return False

            async def defer(self, thinking: bool = True) -> None:
                self.deferred = True

            async def send_message(self, message: str, *, ephemeral: bool = False) -> None:
                self.sent_messages.append(message)

            async def edit_message(self, *, view: object | None = None) -> None:
                self.deferred = True

        response = DummyResponse()
        thread_id = 2468
        class FakeThread:
            def __init__(self, identifier: int) -> None:
                self.id = identifier
                self.parent = None
                self.guild = None
                self.send = AsyncMock()

        monkeypatch.setattr(panels.discord, "Thread", FakeThread)
        thread = FakeThread(thread_id)

        message = SimpleNamespace(id=2, edit=AsyncMock())
        interaction = SimpleNamespace(
            response=response,
            channel=thread,
            user=SimpleNamespace(id=123, display_name="Recruit"),
            message=message,
            id=314,
        )

        send_exception = AsyncMock()
        monkeypatch.setattr(panels.logs, "send_welcome_exception", send_exception)

        view = OpenQuestionsPanelView(controller=controller, thread_id=thread_id)

        button = next(
            child
            for child in view.children
            if getattr(child, "custom_id", None) == OpenQuestionsPanelView.CUSTOM_ID
        )

        await button.callback(interaction)

        controller.get_or_load_questions.assert_awaited_once()
        controller.prompt_retry.assert_not_awaited()
        assert response.deferred is True
        assert response.sent_messages == [view.ERROR_NOTICE]
        interaction.message.edit.assert_awaited_once()

        assert send_exception.await_count == 1
        _, kwargs = send_exception.await_args
        assert kwargs.get("result") == "schema_load_failed"
        assert kwargs.get("error") == error_message

    asyncio.run(runner())
