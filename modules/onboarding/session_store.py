"""In-memory session store for onboarding dialog state."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict

from typing_extensions import TypedDict

TimeoutCallback = Callable[[int], Awaitable[None]]


class PendingStep(TypedDict, total=False):
    """Metadata describing the currently pending onboarding step."""

    kind: str
    index: int


@dataclass
class SessionData:
    """Container for per-thread onboarding dialog state."""

    flow: str
    schema_hash: str | None
    answers: Dict[str, Any] = field(default_factory=dict)
    visibility: Dict[str, Dict[str, str]] = field(default_factory=dict)
    pending_step: PendingStep | None = None
    preview_message_id: int | None = None
    preview_channel_id: int | None = None
    last_active: float = field(default_factory=time.monotonic)
    _timeout_handle: asyncio.TimerHandle | None = field(default=None, repr=False)
    _timeout_callback: TimeoutCallback | None = field(default=None, repr=False)

    def touch(self) -> None:
        """Update the activity timestamp for the session."""

        self.last_active = time.monotonic()


class SessionStore:
    """Simple in-memory store for onboarding dialog sessions."""

    def __init__(self, *, inactivity_timeout: float = 600.0) -> None:
        self._sessions: Dict[int, SessionData] = {}
        self._timeout = inactivity_timeout

    def get(self, thread_id: int) -> SessionData | None:
        """Return the session for ``thread_id`` if it exists."""

        return self._sessions.get(thread_id)

    def ensure(
        self,
        thread_id: int,
        *,
        flow: str,
        schema_hash: str | None,
    ) -> SessionData:
        """Return an existing session or create a new one for ``thread_id``."""

        session = self._sessions.get(thread_id)
        if session and session.schema_hash != schema_hash:
            self.end(thread_id)
            session = None
        if session is None:
            session = SessionData(flow=flow, schema_hash=schema_hash)
            self._sessions[thread_id] = session
        session.flow = flow
        session.schema_hash = schema_hash
        session.touch()
        self._schedule_timeout(thread_id, session)
        return session

    def set_preview_message(
        self,
        thread_id: int,
        *,
        message_id: int | None,
        channel_id: int | None,
    ) -> None:
        """Persist preview message metadata for ``thread_id``."""

        session = self._sessions.get(thread_id)
        if not session:
            return
        session.preview_message_id = message_id
        session.preview_channel_id = channel_id
        session.touch()
        self._schedule_timeout(thread_id, session)

    def set_pending_step(
        self,
        thread_id: int,
        step: PendingStep | None,
    ) -> None:
        """Update the pending step metadata for ``thread_id``."""

        session = self._sessions.get(thread_id)
        if not session:
            return
        session.pending_step = step
        session.touch()
        self._schedule_timeout(thread_id, session)

    def register_timeout_callback(
        self,
        thread_id: int,
        callback: TimeoutCallback | None,
    ) -> None:
        """Assign a coroutine callback executed when the session times out."""

        session = self._sessions.get(thread_id)
        if not session:
            return
        session._timeout_callback = callback
        self._schedule_timeout(thread_id, session)

    def end(self, thread_id: int) -> None:
        """Remove the session and cancel its timeout handler."""

        session = self._sessions.pop(thread_id, None)
        if not session:
            return
        handle = session._timeout_handle
        if handle is not None:
            handle.cancel()

    def _schedule_timeout(self, thread_id: int, session: SessionData) -> None:
        if thread_id not in self._sessions:
            return
        loop = asyncio.get_running_loop()
        if session._timeout_handle is not None:
            session._timeout_handle.cancel()

        if session._timeout_callback is None:
            session._timeout_handle = None
            return

        delay = max(1.0, self._timeout)

        def _runner() -> None:
            asyncio.create_task(self._maybe_timeout(thread_id))

        session._timeout_handle = loop.call_later(delay, _runner)

    async def _maybe_timeout(self, thread_id: int) -> None:
        session = self._sessions.get(thread_id)
        if not session:
            return
        if session._timeout_callback is None:
            session._timeout_handle = None
            return
        now = time.monotonic()
        if now - session.last_active < self._timeout:
            self._schedule_timeout(thread_id, session)
            return
        callback = session._timeout_callback
        self.end(thread_id)
        if callback is not None:
            try:
                await callback(thread_id)
            except Exception:
                # Controllers handle logging; swallow to avoid bubbling to loop.
                pass


store = SessionStore()

__all__ = ["PendingStep", "SessionData", "SessionStore", "store"]

