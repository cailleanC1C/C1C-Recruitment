import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.onboarding.ui import panels
from modules.onboarding.ui.panels import OpenQuestionsPanelView


def test_open_questions_button_has_custom_id() -> None:
    async def runner() -> None:
        view = OpenQuestionsPanelView()
        button_ids = [
            getattr(child, "custom_id", None)
            for child in view.children
            if hasattr(child, "custom_id")
        ]

        assert OpenQuestionsPanelView.CUSTOM_ID in button_ids
        assert view.timeout is None

    asyncio.run(runner())


def test_restart_from_view_responds_before_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        monkeypatch.setattr(panels.diag, "is_enabled", lambda: False)

        class DummyResponse:
            def __init__(self) -> None:
                self.sent_messages: list[str] = []
                self.deferred = False

            def is_done(self) -> bool:
                return bool(self.sent_messages) or self.deferred

            async def send_message(self, message: str, *, ephemeral: bool = False) -> None:
                if self.is_done():
                    raise AssertionError("response already sent")
                self.sent_messages.append(message)

            async def defer(self, ephemeral: bool = False) -> None:
                if self.is_done():
                    raise AssertionError("response already sent")
                self.deferred = True

        response = DummyResponse()

        async def fake_log(level: str, **payload: object) -> None:
            assert response.is_done()

        log_mock = AsyncMock(side_effect=fake_log)
        monkeypatch.setattr(panels.logs, "send_welcome_log", log_mock)

        view = OpenQuestionsPanelView()
        interaction = SimpleNamespace(
            response=response,
            channel=None,
            message=SimpleNamespace(id=1234),
            user=SimpleNamespace(id=5678, display_name="Recruit"),
            followup=None,
        )

        await view._restart_from_view(interaction, {"view": "panel"})

        assert response.is_done()
        assert response.deferred is True
        assert not response.sent_messages
        assert log_mock.await_count >= 1

    asyncio.run(runner())
