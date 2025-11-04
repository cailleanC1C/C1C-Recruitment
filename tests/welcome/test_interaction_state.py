from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


def _reload_modules(monkeypatch: pytest.MonkeyPatch, log_path: str):
    monkeypatch.setenv("WELCOME_DIAG", "1")
    monkeypatch.setenv("WELCOME_DIAG_PATH", log_path)
    diag_module = importlib.reload(importlib.import_module("modules.onboarding.diag"))
    welcome_module = importlib.reload(
        importlib.import_module("modules.onboarding.controllers.welcome_controller")
    )
    return diag_module, welcome_module


def _read_events(log_path: str) -> list[dict[str, object]]:
    path = Path(log_path)
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def test_modal_launch_skips_when_response_done(monkeypatch: pytest.MonkeyPatch, tmp_path):
    log_path = tmp_path / "diag.jsonl"
    _, welcome = _reload_modules(monkeypatch, str(log_path))

    async def runner() -> None:
        controller = welcome.BaseWelcomeController(bot=MagicMock(), flow="welcome")
        thread_id = 987
        thread = SimpleNamespace(id=thread_id, parent_id=654)
        controller._threads[thread_id] = thread
        controller._questions[thread_id] = []
        controller._sources[thread_id] = "test"
        controller._allowed_users[thread_id] = set()

        session = welcome.store.ensure(thread_id, flow=controller.flow, schema_hash="schema")
        session.answers = {}
        session.visibility = {}

        class DummyModal:
            def __init__(self) -> None:
                self.questions: list[str] = []

        monkeypatch.setattr(welcome, "build_modals", lambda *args, **kwargs: [DummyModal()])

        response = SimpleNamespace(
            is_done=MagicMock(return_value=True),
            send_message=AsyncMock(),
        )
        followup = SimpleNamespace(send=AsyncMock())
        app_perms = SimpleNamespace(
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            read_message_history=True,
        )
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            user=SimpleNamespace(id=111, roles=[]),
            channel=SimpleNamespace(id=thread_id, parent_id=654),
            channel_id=thread_id,
            message=SimpleNamespace(id=321),
            app_permissions=app_perms,
        )

        await controller._handle_modal_launch(thread_id, interaction)

        assert response.send_message.await_count == 0

        events = _read_events(str(log_path))
        skipped = [event for event in events if event.get("event") == "inline_launch_skipped"]
        assert skipped, "expected inline_launch_skipped event"
        assert skipped[0].get("response_is_done") is True

        welcome.store.end(thread_id)

    asyncio.run(runner())


def test_safe_ephemeral_logs_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path):
    log_path = tmp_path / "diag.jsonl"
    _, welcome = _reload_modules(monkeypatch, str(log_path))

    async def runner() -> None:
        forbidden_error = discord.Forbidden(response=MagicMock(), message="forbidden")

        response = SimpleNamespace(
            is_done=MagicMock(return_value=False),
            send_message=AsyncMock(side_effect=forbidden_error),
        )
        followup = SimpleNamespace(send=AsyncMock())
        app_perms = SimpleNamespace(
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            read_message_history=True,
        )
        interaction = SimpleNamespace(
            response=response,
            followup=followup,
            user=SimpleNamespace(id=555, roles=[]),
            channel=None,
            channel_id=None,
            message=SimpleNamespace(id=777),
            app_permissions=app_perms,
        )

        await welcome._safe_ephemeral(interaction, "Denied")

        assert response.send_message.await_count == 1

        events = _read_events(str(log_path))
        errors = [event for event in events if event.get("event") == "deny_notice_error"]
        assert errors, "expected deny_notice_error event"
        error_event = errors[0]
        assert error_event.get("error_type") == "Forbidden"
        assert error_event.get("message_id") == 777

    asyncio.run(runner())

