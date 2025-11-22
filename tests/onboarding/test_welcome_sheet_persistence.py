from types import SimpleNamespace

import pytest

from modules.onboarding.controllers import welcome_controller
from modules.onboarding.controllers.welcome_controller import WelcomeController
from modules.onboarding.session_store import SessionData, store


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_schedule_timeout", lambda *_args, **_kwargs: None)
    store._sessions.clear()
    yield
    store._sessions.clear()


def test_persist_session_start_records_sheet_row(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, SessionData] = {}

    monkeypatch.setattr(
        welcome_controller.Session,
        "load_from_sheet",
        classmethod(lambda _cls, _applicant_id, _thread_id: None),
    )

    def _save(session: welcome_controller.Session) -> None:
        saved["session"] = session

    monkeypatch.setattr(welcome_controller.Session, "save_to_sheet", _save)

    controller = WelcomeController(SimpleNamespace())
    thread_id = 101
    controller._target_users[thread_id] = 202
    session = store.ensure(thread_id, flow=controller.flow, schema_hash="hash")

    controller._persist_session_start(
        thread_id,
        panel_message_id=303,
        session_data=session,
    )

    persisted = saved.get("session")
    assert persisted is not None
    assert persisted.thread_id == thread_id
    assert persisted.applicant_id == 202
    assert persisted.panel_message_id == 303
    assert persisted.step_index == 0
    assert persisted.completed is False


def test_persist_session_completion_updates_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, welcome_controller.Session] = {}
    existing = welcome_controller.Session(thread_id=505, applicant_id=606)

    def _load(_cls, applicant_id: int, thread_id: int):
        assert applicant_id == 606
        assert thread_id == 505
        return existing

    def _save(session: welcome_controller.Session) -> None:
        saved["session"] = session

    monkeypatch.setattr(welcome_controller.Session, "load_from_sheet", classmethod(_load))
    monkeypatch.setattr(welcome_controller.Session, "save_to_sheet", _save)

    controller = WelcomeController(SimpleNamespace())
    thread_id = 505
    controller._target_users[thread_id] = 606
    controller._panel_messages[thread_id] = 707
    session = store.ensure(thread_id, flow=controller.flow, schema_hash="hash")
    session.current_question_index = 1
    controller._questions[thread_id] = [SimpleNamespace(qid="q1"), SimpleNamespace(qid="q2")]

    answers = {"q1": "yes"}

    controller._persist_session_completion(
        thread_id,
        session_data=session,
        answers=answers,
        panel_message_id=controller._panel_messages.get(thread_id),
    )

    persisted = saved.get("session")
    assert persisted is existing
    assert persisted.completed is True
    assert persisted.completed_at is not None
    assert persisted.panel_message_id == 707
    assert persisted.answers == answers
    assert persisted.step_index == 1
