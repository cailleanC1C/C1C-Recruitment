from types import SimpleNamespace

import pytest

from modules.onboarding.controllers.welcome_controller import WelcomeController
from modules.onboarding.session_store import store


def _question(qid: str) -> SimpleNamespace:
    return SimpleNamespace(
        qid=qid,
        label=qid,
        type="short",
        options=[],
        required=True,
        nav_rules="",
        visibility_rules="",
    )


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_schedule_timeout", lambda *_args, **_kwargs: None)
    try:
        store._sessions.clear()
    except Exception:  # pragma: no cover - defensive cleanup
        for thread_id in list(getattr(store, "_sessions", {}).keys()):
            store.end(thread_id)
    yield
    try:
        store._sessions.clear()
    except Exception:  # pragma: no cover - defensive cleanup
        for thread_id in list(getattr(store, "_sessions", {}).keys()):
            store.end(thread_id)


def test_set_current_step_updates_pending_and_current_index() -> None:
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 101
    controller._questions[thread_id] = [_question("q1"), _question("q2")]

    session = store.ensure(thread_id, flow=controller.flow, schema_hash="hash")
    store.set_pending_step(thread_id, {"kind": "inline", "index": 0})
    session.current_question_index = 0

    updated = controller._set_current_step_for_thread(thread_id, 1)

    assert updated is session
    assert session.current_question_index == 1
    assert session.pending_step == {"kind": "inline", "index": 1}

    inline_index, capture_mode = controller._resolve_inline_index(thread_id, session)
    assert inline_index == 1
    assert capture_mode == "pending"


def test_set_current_step_rejects_out_of_range() -> None:
    bot = SimpleNamespace()
    controller = WelcomeController(bot)
    thread_id = 202
    controller._questions[thread_id] = [_question("q1"), _question("q2")]

    session = store.ensure(thread_id, flow=controller.flow, schema_hash="hash")
    store.set_pending_step(thread_id, {"kind": "inline", "index": 0})
    session.current_question_index = 0

    updated = controller._set_current_step_for_thread(thread_id, 5)

    assert updated is None
    assert session.current_question_index == 0
    assert session.pending_step == {"kind": "inline", "index": 0}
