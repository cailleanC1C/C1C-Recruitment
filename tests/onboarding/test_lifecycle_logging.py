import asyncio
import logging
from types import SimpleNamespace

import pytest

from modules.onboarding import logs, welcome_flow, watcher_welcome
from modules.onboarding.session_store import store
from modules.onboarding.ui import panels
from modules.onboarding.controllers import welcome_controller
from modules.onboarding import thread_scopes
from modules.common import feature_flags
from shared.sheets import onboarding_questions


class DummyParent:
    def __init__(self, name: str = "welcome") -> None:
        self.name = name
        self.category = SimpleNamespace(name="WELCOME CENTER")


class DummyThread:
    def __init__(self, name: str = "W0481-caillean") -> None:
        self.name = name
        self.id = 4242
        self.parent = DummyParent()

    async def send(self, *_, **__):
        return SimpleNamespace(id=999)


def test_lifecycle_helper_formats_neutral(monkeypatch, caplog):
    sent: list[str] = []

    async def fake_send(message: str) -> None:
        sent.append(message)

    monkeypatch.setattr(logs.rt, "send_log_message", fake_send)
    caplog.set_level(logging.INFO, logger="c1c.onboarding.logs")

    async def runner() -> None:
        await logs.log_onboarding_panel_lifecycle(
            event="open",
            ticket="W0481-caillean",
            actor="@Recruit",
            channel="#WELCOME CENTER › welcome",
            questions=16,
            schema_version="abcdef123456",
        )

    asyncio.run(runner())

    assert sent, "expected log message"
    assert sent[0].startswith("[watcher|lifecycle] 📘 welcome_panel_open"), sent[0]
    assert "\n• channel=#WELCOME CENTER › welcome • questions=16" in sent[0]
    assert "schema=" not in sent[0]
    assert "message_id" not in sent[0]
    assert any("📘 welcome_panel_open" in record.getMessage() for record in caplog.records)


def test_lifecycle_helper_hides_reason_when_info(monkeypatch):
    sent: list[str] = []

    async def fake_send(message: str) -> None:
        sent.append(message)

    monkeypatch.setattr(logs.rt, "send_log_message", fake_send)

    async def runner() -> None:
        await logs.log_onboarding_panel_lifecycle(
            event="open",
            ticket="W0481-caillean",
            actor="@Recruit",
            channel="#WELCOME CENTER › welcome",
            questions=16,
            schema_version="v1",
            reason="should_hide",
        )

    asyncio.run(runner())

    assert sent and "reason=should_hide" not in sent[0]


def test_welcome_watcher_logs_open_once(monkeypatch):
    recorded: list[dict[str, object]] = []

    async def fake_lifecycle_log(**payload):
        recorded.append(payload)

    async def ensure_membership(_thread):
        return True, None

    monkeypatch.setattr(logs, "log_onboarding_panel_lifecycle", fake_lifecycle_log)
    monkeypatch.setattr(logs, "question_stats", lambda flow: (16, "v1"))
    monkeypatch.setattr(watcher_welcome.thread_membership, "ensure_thread_membership", ensure_membership)
    monkeypatch.setattr(panels, "OpenQuestionsPanelView", lambda: SimpleNamespace())

    watcher = watcher_welcome.WelcomeWatcher(bot=SimpleNamespace())
    thread = DummyThread()
    actor = SimpleNamespace(display_name="Recruit", bot=False)

    async def runner() -> None:
        await watcher._post_panel(thread, actor=actor, source="phrase")

    asyncio.run(runner())

    assert recorded and recorded[0]["event"] == "open"


def test_welcome_watcher_logs_missing_ticket(monkeypatch):
    recorded: list[dict[str, object]] = []

    async def fake_lifecycle_log(**payload):
        recorded.append(payload)

    async def ensure_membership(_thread):
        return True, None

    monkeypatch.setattr(logs, "log_onboarding_panel_lifecycle", fake_lifecycle_log)
    monkeypatch.setattr(logs, "question_stats", lambda flow: (16, "v1"))
    monkeypatch.setattr(watcher_welcome.thread_membership, "ensure_thread_membership", ensure_membership)
    monkeypatch.setattr(panels, "OpenQuestionsPanelView", lambda: SimpleNamespace())

    watcher = watcher_welcome.WelcomeWatcher(bot=SimpleNamespace())
    thread = DummyThread(name="no-ticket")
    actor = SimpleNamespace(display_name="Recruit", bot=False)

    async def runner() -> None:
        await watcher._post_panel(thread, actor=actor, source="phrase")

    asyncio.run(runner())

    assert recorded and recorded[0]["result"] == "skipped"
    assert recorded[0]["reason"] == "ticket_not_parsed"


def test_start_welcome_dialog_logs_once(monkeypatch):
    recorded: list[dict[str, object]] = []

    async def fake_lifecycle_log(**payload):
        recorded.append(payload)

    monkeypatch.setattr(logs, "log_onboarding_panel_lifecycle", fake_lifecycle_log)
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: True)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: False)
    monkeypatch.setattr(feature_flags, "is_enabled", lambda name: True)
    monkeypatch.setattr(onboarding_questions, "get_questions", lambda flow: [object(), object()])
    monkeypatch.setattr(onboarding_questions, "schema_hash", lambda flow: "abcdef1234")

    async def fake_locate(_thread):
        return SimpleNamespace()

    monkeypatch.setattr(welcome_flow, "locate_welcome_message", fake_locate)
    monkeypatch.setattr(welcome_flow, "extract_target_from_message", lambda _msg: (None, None))

    class DummyController:
        flow = "welcome"

        def __init__(self, _bot):
            self._panel_messages = {}
            self._prefetched_panels = {}
            self._sources = {}

        async def run(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(welcome_flow, "WelcomeController", DummyController)
    monkeypatch.setattr(welcome_flow, "PromoController", DummyController)
    monkeypatch.setattr(panels, "register_panel_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(welcome_flow, "_resolve_bot", lambda _thread: SimpleNamespace())

    thread = DummyThread()
    actor = SimpleNamespace(display_name="Recruit", bot=False)

    async def runner() -> None:
        await welcome_flow.start_welcome_dialog(thread, actor, source="ticket", bot=SimpleNamespace())

    asyncio.run(runner())

    assert recorded and recorded[0]["event"] == "start"


def test_panel_restart_logs_once(monkeypatch):
    recorded: list[dict[str, object]] = []

    async def fake_lifecycle_log(**payload):
        recorded.append(payload)

    async def fake_notify(self, _interaction):
        return None

    async def fake_start(*_args, **_kwargs):
        return None

    monkeypatch.setattr(logs, "log_onboarding_panel_lifecycle", fake_lifecycle_log)
    monkeypatch.setattr(logs, "question_stats", lambda flow: (16, "v1"))
    monkeypatch.setattr(panels.OpenQuestionsPanelView, "_notify_restart", fake_notify, raising=False)
    monkeypatch.setattr(welcome_flow, "start_welcome_dialog", fake_start)

    base_thread = type("_RestartThread", (), {})
    monkeypatch.setattr(panels.discord, "Thread", base_thread)

    class PanelThread(base_thread):
        def __init__(self):
            self.id = 123
            self.name = "W0481-caillean"
            self.parent = DummyParent()

    async def runner() -> None:
        thread = PanelThread()
        interaction = SimpleNamespace(
            channel=thread,
            user=SimpleNamespace(display_name="Recruit"),
            client=SimpleNamespace(),
            message=SimpleNamespace(id=1),
        )
        view = panels.OpenQuestionsPanelView()
        view.controller = SimpleNamespace(flow="welcome")
        await view._restart_from_view(interaction, {})

    asyncio.run(runner())

    assert recorded and recorded[0]["event"] == "restart"


def test_completion_logging_helper(monkeypatch):
    recorded: list[dict[str, object]] = []

    async def fake_lifecycle_log(**payload):
        recorded.append(payload)

    monkeypatch.setattr(logs, "log_onboarding_panel_lifecycle", fake_lifecycle_log)

    controller = welcome_controller.WelcomeController(bot=SimpleNamespace())
    thread_id = 777
    thread = DummyThread()
    controller._threads[thread_id] = thread
    controller._questions[thread_id] = [SimpleNamespace(qid="w_level_detail")]
    answers = {"w_level_detail": "Late Game"}

    async def runner() -> None:
        session = store.ensure(thread_id, flow="welcome", schema_hash="schema1")
        try:
            await controller._log_panel_completion(
                thread_id,
                thread=thread,
                actor=SimpleNamespace(display_name="Recruit"),
                session=session,
                answers=answers,
            )
        finally:
            store._sessions.clear()

    asyncio.run(runner())
    assert recorded and recorded[0]["event"] == "complete"
    assert recorded[0]["extras"]["level_detail"] == "Late Game"
