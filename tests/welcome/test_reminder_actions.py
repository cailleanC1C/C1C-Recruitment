from datetime import datetime, timedelta, timezone

from modules.onboarding.sessions import Session
from modules.onboarding import watcher_welcome


def _dt(hours: float) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


def test_reminder_triggers_when_no_progress():
    now = _dt(6)
    created = _dt(0)
    action = watcher_welcome._determine_reminder_action(
        now, created, None, has_progress=False
    )
    assert action == "reminder"


def test_reminder_skipped_when_progress_exists():
    now = _dt(6)
    created = _dt(0)
    session = Session(thread_id=1, applicant_id=2)
    session.answers = {"w_ign": "C1C"}
    action = watcher_welcome._determine_reminder_action(
        now, created, session, has_progress=True
    )
    assert action is None


def test_warning_after_one_day():
    now = _dt(25)
    created = _dt(0)
    action = watcher_welcome._determine_reminder_action(
        now, created, None, has_progress=False
    )
    assert action == "warning"


def test_auto_close_after_threshold_even_if_warning_sent():
    now = _dt(37)
    created = _dt(0)
    session = Session(thread_id=1, applicant_id=2)
    session.warning_sent_at = _dt(25)
    action = watcher_welcome._determine_reminder_action(
        now, created, session, has_progress=False
    )
    assert action == "close"


def test_completed_sessions_skip_actions():
    now = _dt(40)
    created = _dt(0)
    session = Session(thread_id=1, applicant_id=2)
    session.completed = True
    action = watcher_welcome._determine_reminder_action(
        now, created, session, has_progress=False
    )
    assert action is None
