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
    assert "Press **Enter answer** to respond." in text

    controller.answers_by_thread[thread_id] = {"ign": "Ace"}
    text_with_answer = controller.render_step(thread_id, 0)
    assert "Press **Enter answer** to respond." not in text_with_answer

