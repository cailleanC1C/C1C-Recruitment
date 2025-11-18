from types import SimpleNamespace

import pytest

from modules.onboarding.controllers.welcome_controller import WelcomeController
from modules.onboarding.session_store import store


def test_render_step_prompts_for_text_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "get", lambda _thread_id: None)
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 4242
    question = SimpleNamespace(label="IGN", qid="ign", options=[], type="short", required=False)
    controller._questions[thread_id] = [question]
    controller.answers_by_thread[thread_id] = {}

    text = controller.render_step(thread_id, 0)
    assert "Just reply in this thread with your answer." in text

    controller.answers_by_thread[thread_id] = {"ign": "Ace"}
    text_with_answer = controller.render_step(thread_id, 0)
    assert "Just reply in this thread with your answer." in text_with_answer


def test_render_step_formats_heading_and_help(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(visibility={"ign": {"state": "show"}}, answers={})
    monkeypatch.setattr(store, "get", lambda _thread_id: session)
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 99
    question = SimpleNamespace(
        label="What's your IGN?",
        qid="ign",
        options=[],
        type="short",
        required=False,
        help="Use the name you play with.",
    )
    controller._questions[thread_id] = [question]
    controller.answers_by_thread[thread_id] = {}

    text = controller.render_step(thread_id, 0)
    assert text.startswith("**Onboarding • 1/1**")
    assert "## What's your IGN?" in text
    assert "_Use the name you play with._" in text


def test_render_step_marks_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(visibility={"ign": {"state": "optional"}}, answers={})
    monkeypatch.setattr(store, "get", lambda _thread_id: session)
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 7
    question = SimpleNamespace(label="IGN", qid="ign", options=[], type="short", required=True, help="")
    controller._questions[thread_id] = [question]
    controller.answers_by_thread[thread_id] = {}

    text = controller.render_step(thread_id, 0)
    assert text.startswith("**Onboarding • 1/1 • Input is optional**")

