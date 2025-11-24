import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.onboarding import watcher_welcome


class DummyComponent(SimpleNamespace):
    pass


class DummyMessage(SimpleNamespace):
    pass


class DummyThread:
    def __init__(self, name: str = "R0001-recruit", parent_id: int = 2024):
        self.name = name
        self.parent_id = parent_id
        self.id = 4242
        self.parent = SimpleNamespace()
        self.messages: list[DummyMessage] = []

    async def history(self, limit: int = 20):  # pragma: no cover - used in helper
        for message in list(self.messages)[-limit:]:
            yield message

    async def send(self, content=None, view=None):
        message = DummyMessage(content=content, view=view, components=[])
        self.messages.append(message)
        return message

@pytest.fixture(autouse=True)
def patch_feature_flags(monkeypatch):
    monkeypatch.setattr(
        watcher_welcome.feature_flags,
        "is_enabled",
        lambda name: True,
    )
    monkeypatch.setattr(watcher_welcome, "get_ticket_tool_bot_id", lambda: 5555)
    monkeypatch.setattr(watcher_welcome.thread_scopes, "is_promo_parent", lambda _thread: True)
    monkeypatch.setattr(watcher_welcome.logs, "question_stats", lambda flow: (1, "v1"))
    monkeypatch.setattr(watcher_welcome.discord, "Thread", DummyThread)
    return None


def test_promo_greeting_posts_panel(monkeypatch):
    recorded = []

    async def capture_log(**payload):
        recorded.append(payload)

    monkeypatch.setattr(watcher_welcome.feature_flags, "is_enabled", lambda name: True)
    monkeypatch.setattr(watcher_welcome.thread_scopes, "is_promo_parent", lambda _thread: True)
    monkeypatch.setattr(watcher_welcome, "get_ticket_tool_bot_id", lambda: 5555)

    monkeypatch.setattr(watcher_welcome.logs, "log_onboarding_panel_lifecycle", capture_log)
    ensure_membership = AsyncMock(return_value=(True, None))

    monkeypatch.setattr(watcher_welcome.thread_membership, "ensure_thread_membership", ensure_membership)
    monkeypatch.setattr(watcher_welcome.panels, "OpenQuestionsPanelView", lambda: SimpleNamespace())

    async def no_panel(*_args, **_kwargs):
        return None

    monkeypatch.setattr(watcher_welcome.panels, "find_panel_message", no_panel)

    watcher = watcher_welcome.WelcomeWatcher(bot=SimpleNamespace(user=SimpleNamespace(id=1111)))
    thread = DummyThread()
    author = SimpleNamespace(id=5555, bot=True)
    async def add_reaction(_emoji):
        return None

    message = SimpleNamespace(
        channel=thread,
        author=author,
        content="Hello <!-- trigger:promo.r -->",
        add_reaction=add_reaction,
    )

    asyncio.run(watcher.on_message(message))

    assert ensure_membership.await_count == 1
    assert recorded and recorded[0].get("result") not in {"error", "skipped"}
    assert any(msg.content for msg in thread.messages)


def test_promo_panel_dedup(monkeypatch):
    recorded = []

    async def capture_log(**payload):
        recorded.append(payload)

    monkeypatch.setattr(watcher_welcome.feature_flags, "is_enabled", lambda name: True)
    monkeypatch.setattr(watcher_welcome.thread_scopes, "is_promo_parent", lambda _thread: True)
    monkeypatch.setattr(watcher_welcome, "get_ticket_tool_bot_id", lambda: 5555)

    existing = DummyMessage(
        components=[DummyComponent(children=[DummyComponent(custom_id=watcher_welcome.panels.OPEN_QUESTIONS_CUSTOM_ID)])]
    )

    monkeypatch.setattr(watcher_welcome.logs, "log_onboarding_panel_lifecycle", capture_log)

    async def existing_panel(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(watcher_welcome.panels, "find_panel_message", existing_panel)
    ensure_membership = AsyncMock(return_value=(True, None))

    monkeypatch.setattr(watcher_welcome.thread_membership, "ensure_thread_membership", ensure_membership)
    monkeypatch.setattr(watcher_welcome.panels, "OpenQuestionsPanelView", lambda: SimpleNamespace())

    watcher = watcher_welcome.WelcomeWatcher(bot=SimpleNamespace(user=SimpleNamespace(id=1111)))
    thread = DummyThread()
    author = SimpleNamespace(id=5555, bot=True)
    async def add_reaction(_emoji):
        return None

    message = SimpleNamespace(
        channel=thread,
        author=author,
        content="Hello <!-- trigger:promo.l -->",
        add_reaction=add_reaction,
    )

    asyncio.run(watcher.on_message(message))

    assert ensure_membership.await_count == 1
    assert recorded and recorded[0].get("reason") == "panel_exists"
    assert not thread.messages
