import pytest

from modules.onboarding.sessions import Session


@pytest.fixture
def session_factory():
    def _build(thread_id: int = 999, applicant_id: int = 321) -> Session:
        return Session(thread_id=thread_id, applicant_id=applicant_id)

    return _build


def test_session_round_trip_sheet(session_factory, monkeypatch):
    saved: dict[str, object] = {}

    import shared.sheets.onboarding_sessions as sheet_module

    monkeypatch.setattr(sheet_module, "save", lambda payload: saved.update(payload))
    monkeypatch.setattr(sheet_module, "load", lambda uid, tid: saved if saved else None)

    session = session_factory()
    session.answers = {"w_ign": "Caillean", "w_stage": "Early Game"}
    session.step_index = 2

    session.save_to_sheet()

    restored = Session.load_from_sheet(session.thread_id, session.applicant_id)
    assert restored is not None
    assert restored.answers.get("w_ign") == "Caillean"
    assert restored.step_index == 2
