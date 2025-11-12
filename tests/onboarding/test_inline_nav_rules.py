from types import SimpleNamespace

import pytest

from modules.onboarding.controllers.welcome_controller import WelcomeController
from modules.onboarding.session_store import store


def _question(qid: str, *, nav_rules: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        qid=qid,
        label=qid,
        type="short",
        options=[],
        required=True,
        nav_rules=nav_rules,
        visibility_rules="",
    )


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(visibility={}, answers={})
    monkeypatch.setattr(store, "get", lambda _thread_id: session)


def test_nav_rules_skip_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 77

    questions = [
        _question(
            "w_siege",
            nav_rules='goto_if(value = "yes", target = "w_siege_detail")\n'
            'goto_if(value = "no", target = "w_cvc")',
        ),
        _question("w_siege_detail"),
        _question(
            "w_cvc",
            nav_rules='goto_if(int(value) >= 3, target="w_cvc_points")\n'
            'goto_if(int(value) < 3, target="w_origin")',
        ),
        _question("w_cvc_points"),
        _question("w_origin"),
    ]

    controller._questions[thread_id] = questions
    controller.answers_by_thread[thread_id] = {"w_siege": "no"}

    next_index = controller.next_visible_step(thread_id, 0)
    assert next_index == 2


def test_nav_rules_include_followup_when_condition_met(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 88

    questions = [
        _question("w_intro"),
        _question(
            "w_cvc",
            nav_rules='goto_if(int(value) >= 3, target="w_cvc_points")\n'
            'goto_if(int(value) < 3, target="w_wrap")',
        ),
        _question("w_cvc_points"),
        _question("w_wrap"),
    ]

    controller._questions[thread_id] = questions

    controller.answers_by_thread[thread_id] = {"w_cvc": "2"}
    skip_points = controller.next_visible_step(thread_id, 1)
    assert skip_points == 3

    controller.answers_by_thread[thread_id] = {"w_cvc": "3"}
    include_points = controller.next_visible_step(thread_id, 1)
    assert include_points == 2

