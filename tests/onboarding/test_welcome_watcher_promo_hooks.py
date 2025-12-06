import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.onboarding import watcher_promo, watcher_welcome
from modules.onboarding.watcher_welcome import PanelOutcome


class DummyThread:
    def __init__(self, name: str = "R0001-recruit", parent_id: int = 2024):
        self.name = name
        self.parent_id = parent_id
        self.id = 4242
        self.parent = SimpleNamespace()
        self.messages: list[SimpleNamespace] = []


@pytest.fixture()
def promo_context() -> watcher_promo.PromoTicketContext:
    return watcher_promo.PromoTicketContext(
        thread_id=4242,
        ticket_number="R0001",
        username="recruit",
        promo_type="returning player",
        thread_created="2025-11-24 00:00:00",
        year="2025",
        month="November",
    )


@pytest.fixture()
def promo_watcher(monkeypatch, promo_context):
    monkeypatch.setattr(watcher_promo.feature_flags, "is_enabled", lambda name: True)
    monkeypatch.setattr(watcher_promo, "get_ticket_tool_bot_id", lambda: 5555)
    monkeypatch.setattr(watcher_promo, "get_promo_channel_id", lambda: 2024)
    monkeypatch.setattr(watcher_promo.thread_scopes, "is_promo_parent", lambda _thread: True)
    monkeypatch.setattr(watcher_promo.discord, "Thread", DummyThread)

    watcher = watcher_promo.PromoTicketWatcher(bot=SimpleNamespace(user=SimpleNamespace(id=1111)))
    monkeypatch.setattr(watcher, "_ensure_context", AsyncMock(return_value=promo_context))

    return watcher


def test_promo_greeting_posts_panel(monkeypatch, promo_watcher):
    recorded: list[dict] = []

    async def fake_post_panel(bot, thread, *, actor, flow, ticket_code=None, trigger_message=None):
        recorded.append({"flow": flow, "actor": actor, "thread": thread})
        return PanelOutcome("panel_created", None, "R0001", getattr(thread, "name", None), 5)

    events: list[dict] = []

    def capture_log_lifecycle(_logger, scope, event, **fields):  # pragma: no cover - test stub
        events.append({"scope": scope, "event": event, **fields})
        return ""

    monkeypatch.setattr(watcher_promo, "post_open_questions_panel", AsyncMock(side_effect=fake_post_panel))
    monkeypatch.setattr(watcher_promo, "log_lifecycle", capture_log_lifecycle)

    thread = DummyThread()
    author = SimpleNamespace(id=5555, bot=True)
    message = SimpleNamespace(channel=thread, author=author, content="Hello <!-- trigger:promo.r -->")

    asyncio.run(promo_watcher.on_message(message))

    watcher_promo.post_open_questions_panel.assert_awaited_once()
    assert recorded and recorded[0]["flow"] == "promo.r"
    logged = [event for event in events if event.get("event") == "triggered"]
    assert logged and logged[0].get("trigger") == "promo.r"


def test_promo_panel_dedup(monkeypatch, promo_watcher):
    events: list[dict] = []

    async def fake_post_panel(bot, thread, *, actor, flow, ticket_code=None, trigger_message=None):
        return PanelOutcome("skipped", "panel_exists", "R0001", getattr(thread, "name", None), 7)

    def capture_log_lifecycle(_logger, scope, event, **fields):  # pragma: no cover - test stub
        events.append({"scope": scope, "event": event, **fields})
        return ""

    monkeypatch.setattr(watcher_promo, "post_open_questions_panel", AsyncMock(side_effect=fake_post_panel))
    monkeypatch.setattr(watcher_promo, "log_lifecycle", capture_log_lifecycle)

    thread = DummyThread()
    author = SimpleNamespace(id=5555, bot=True)
    message = SimpleNamespace(channel=thread, author=author, content="Hello <!-- trigger:promo.l -->")

    asyncio.run(promo_watcher.on_message(message))

    watcher_promo.post_open_questions_panel.assert_awaited_once()
    logged = [event for event in events if event.get("event") == "triggered"]
    assert logged and logged[0].get("reason") == "panel_exists"


def test_welcome_watcher_declines_promo_thread(monkeypatch):
    parsed = watcher_welcome.parse_welcome_thread_name("L0005-caillean")
    assert parsed is None


def test_promo_logs_scope_for_leadership_panel(monkeypatch):
    recorded: list[dict] = []

    async def fake_log_onboarding(**payload):
        recorded.append(payload)

    monkeypatch.setattr(
        watcher_welcome.logs, "log_onboarding_panel_lifecycle", fake_log_onboarding
    )
    monkeypatch.setattr(watcher_welcome.logs, "question_stats", lambda flow: (1, "v1"))
    monkeypatch.setattr(
        watcher_welcome.thread_membership,
        "ensure_thread_membership",
        AsyncMock(return_value=(True, None)),
    )
    monkeypatch.setattr(watcher_welcome.panels, "find_panel_message", AsyncMock(return_value=None))
    monkeypatch.setattr(watcher_welcome.panels, "OpenQuestionsPanelView", lambda: SimpleNamespace())
    monkeypatch.setattr(
        watcher_welcome.welcome_flow,
        "resolve_onboarding_flow",
        lambda _thread: SimpleNamespace(flow="promo.l", error=None),
    )

    class MiniThread(DummyThread):
        def __init__(self):
            super().__init__(name="L0005-caillean", parent_id=2024)
            self.parent = SimpleNamespace()

        async def send(self, *_args, **_kwargs):  # pragma: no cover - patched send
            return None

    thread = MiniThread()
    actor = SimpleNamespace(display_name="Actor", bot=False)

    outcome = asyncio.run(
        watcher_promo.post_open_questions_panel(
            SimpleNamespace(user=SimpleNamespace(id=1)),
            thread,
            actor=actor,
            flow="promo.l",
        )
    )

    assert outcome.result == "panel_created"
    assert recorded and recorded[0].get("scope") == "promo.l"
    assert recorded[0].get("result") == "panel_created"
