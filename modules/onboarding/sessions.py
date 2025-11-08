"""Session management helpers for the onboarding wizard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Tuple


def utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass
class Session:
    thread_id: int
    applicant_id: int
    panel_message_id: int | None = None
    step_index: int = 0
    answers: Dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    last_updated: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.last_updated = self.created_at

    def reset(self) -> None:
        """Reset the wizard state for the session."""

        self.step_index = 0
        self.answers.clear()
        self.last_updated = utc_now()

    # PR-B: answer helpers
    def set_answer(self, gid: str, value) -> None:
        self.answers[gid] = value
        self.last_updated = utc_now()

    def has_answer(self, gid: str) -> bool:
        return gid in self.answers and self.answers[gid] not in (None, "", "—", [])

    def get_answer(self, gid: str, default=None):
        return self.answers.get(gid, default)


class SessionStore:
    """In-memory store for onboarding wizard sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[Tuple[int, int], Session] = {}

    async def load(self, thread_id: int, applicant_id: int) -> Session:
        key = (thread_id, applicant_id)
        session = self._sessions.get(key)
        if session is None:
            session = Session(thread_id=thread_id, applicant_id=applicant_id)
            self._sessions[key] = session
        return session

    async def save(self, session: Session) -> Session:
        key = (session.thread_id, session.applicant_id)
        self._sessions[key] = session
        session.last_updated = utc_now()
        return session


store = SessionStore()

__all__ = ["Session", "SessionStore", "store", "utc_now"]

