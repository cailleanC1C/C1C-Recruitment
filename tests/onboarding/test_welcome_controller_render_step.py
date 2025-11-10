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
    assert text.startswith("**Onboarding • 1/1**")
    assert "## IGN" in text
    assert "Press **Enter answer** to respond." in text

    controller.answers_by_thread[thread_id] = {"ign": "Ace"}
    text_with_answer = controller.render_step(thread_id, 0)
    assert "Press **Enter answer** to respond." not in text_with_answer
    assert "**Current answer:** Ace" in text_with_answer


def test_render_step_includes_help_and_bool_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "get", lambda _thread_id: None)
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 9001
    question = SimpleNamespace(label="Siege?", qid="siege", options=[], type="bool", required=True, help="Answer honestly.")
    controller._questions[thread_id] = [question]
    controller.answers_by_thread[thread_id] = {}

    text = controller.render_step(thread_id, 0)
    assert "Tap **Yes** or **No** below." in text
    assert "_Answer honestly._" in text

    controller.answers_by_thread[thread_id] = {"siege": "yes"}
    answered = controller.render_step(thread_id, 0)
    assert "**Current answer:** Yes" in answered


def test_visible_navigation_skips_hidden_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(visibility={"q2": {"state": "skip"}}, answers={})
    monkeypatch.setattr(store, "get", lambda tid: session if tid == 77 else None)
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 77
    q1 = SimpleNamespace(label="A", qid="q1", options=[], type="short", required=True)
    q2 = SimpleNamespace(label="B", qid="q2", options=[], type="short", required=True)
    q3 = SimpleNamespace(label="C", qid="q3", options=[], type="short", required=True)
    controller._questions[thread_id] = [q1, q2, q3]

    assert controller.next_visible_step(thread_id, 0) == 2
    assert controller.previous_visible_step(thread_id, 2) == 0

    text = controller.render_step(thread_id, 0)
    assert "## A" in text
    # Rendering step 1 should skip hidden question and show C
    text_after_skip = controller.render_step(thread_id, 1)
    assert "## C" in text_after_skip

