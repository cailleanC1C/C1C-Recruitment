"""Session management helpers for the onboarding wizard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from shared.sheets import onboarding_sessions as sess_sheet


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
    completed: bool = False
    completed_at: datetime | None = None

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

    def mark_completed(self) -> None:
        self.completed = True
        self.completed_at = utc_now()

    # === Sheet persistence helpers ===
    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "applicant_id": self.applicant_id,
            "panel_message_id": self.panel_message_id,
            "step_index": self.step_index,
            "answers": dict(self.answers),
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def save_to_sheet(self) -> None:
        payload = {
            "user_id": int(self.applicant_id),
            "thread_id": int(self.thread_id),
            "panel_message_id": int(self.panel_message_id or 0),
            "step_index": int(self.step_index),
            "answers": self.answers,
            "completed": bool(self.completed),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        sess_sheet.save(payload)

    @classmethod
    def load_from_sheet(cls, thread_id: int, applicant_id: int) -> Optional["Session"]:
        row = sess_sheet.load(int(applicant_id), int(thread_id))
        if not row:
            return None
        panel_id = row.get("panel_message_id") or None
        session = cls(thread_id=int(thread_id), applicant_id=int(applicant_id), panel_message_id=panel_id)
        session.step_index = int(row.get("step_index", 0) or 0)
        answers = row.get("answers") or {}
        if isinstance(answers, dict):
            session.answers = dict(answers)
        else:
            session.answers = {}
        session.completed = bool(row.get("completed", False))
        completed_at = row.get("completed_at")
        if completed_at:
            try:
                normalized = str(completed_at).replace("Z", "+00:00")
                session.completed_at = datetime.fromisoformat(normalized)
            except Exception:
                session.completed_at = None
        session.last_updated = utc_now()
        return session


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

