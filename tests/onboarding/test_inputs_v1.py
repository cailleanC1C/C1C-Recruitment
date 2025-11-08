import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import discord

from modules.onboarding.controllers.wizard import WizardController
from modules.onboarding.sessions import Session, SessionStore


class _DummyRenderer:
    def __init__(self) -> None:
        self.questions: list[dict] = []

    def render(self, session: Session):
        return ("fallback", discord.ui.View())

    def get_question(self, index: int) -> dict:
        return self.questions[index]


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@pytest.fixture
def interaction(event_loop):
    message = MagicMock()
    message.id = 999
    message.edit = AsyncMock()
    channel = SimpleNamespace(
        id=123,
        send=AsyncMock(return_value=message),
        fetch_message=AsyncMock(return_value=message),
    )
    response = SimpleNamespace(
        defer_update=AsyncMock(),
        send_modal=AsyncMock(),
    )
    followup = SimpleNamespace(send=AsyncMock())
    client = SimpleNamespace(loop=event_loop)
    return SimpleNamespace(
        client=client,
        channel=channel,
        response=response,
        followup=followup,
        message=message,
        user=SimpleNamespace(id=555),
    )


@pytest.fixture
def controller(event_loop):
    class _Bot:
        def __init__(self, loop):
            self.loop = loop
            self.logger = MagicMock()

    bot = _Bot(event_loop)
    sessions = SessionStore()
    renderer = _DummyRenderer()
    ctrl = WizardController(bot, sessions, renderer)
    ctrl.renderer.render = lambda session: ("legacy", discord.ui.View())
    return ctrl


@pytest.fixture
def session_factory():
    def _build(thread_id: int = 123, applicant_id: int = 555) -> Session:
        return Session(thread_id=thread_id, applicant_id=applicant_id)

    return _build


def _flush(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


def test_required_text_gates_next(interaction, controller, session_factory):
    session = session_factory()
    controller.renderer.questions = [
        {
            "gid": "w_ign",
            "label": "IGN",
            "type": "short",
            "required": "TRUE",
            "help": "",
            "maxlen": 20,
        }
    ]

    loop = controller.bot.loop
    loop.run_until_complete(controller.sessions.save(session))
    loop.run_until_complete(controller.launch(interaction))
    _flush(loop)

    loop.run_until_complete(
        controller._save_modal_answer(
            interaction,
            session,
            controller.renderer.get_question(0),
            "Caillean",
        )
    )
    _flush(loop)

    assert session.answers["w_ign"] == "Caillean"


def test_bool_buttons_store_value(interaction, controller, session_factory):
    session = session_factory()
    controller.renderer.questions = [
        {
            "gid": "w_siege",
            "label": "Siege?",
            "type": "bool",
            "required": "TRUE",
        }
    ]

    loop = controller.bot.loop
    loop.run_until_complete(controller.sessions.save(session))
    loop.run_until_complete(controller.launch(interaction))
    _flush(loop)

    loop.run_until_complete(
        controller._save_bool_answer(
            interaction,
            session,
            controller.renderer.get_question(0),
            True,
        )
    )
    _flush(loop)

    assert session.answers["w_siege"] is True
