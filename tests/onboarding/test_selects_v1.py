import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from modules.onboarding.controllers.wizard import WizardController
from modules.onboarding.sessions import Session, SessionStore
from modules.onboarding.ui import render_selects as srender


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _build_controller(event_loop: asyncio.AbstractEventLoop) -> WizardController:
    class _Bot:
        def __init__(self, loop):
            self.loop = loop
            self.logger = MagicMock()

    bot = _Bot(event_loop)
    sessions = SessionStore()
    renderer = SimpleNamespace(get_question=lambda _: {})
    controller = WizardController(bot, sessions, renderer)
    controller.renderer.render = lambda session: ("legacy", discord.ui.View())
    return controller


def _build_interaction(loop: asyncio.AbstractEventLoop):
    message = MagicMock()
    message.id = 42
    message.edit = AsyncMock()
    channel = SimpleNamespace(
        id=123,
        send=AsyncMock(return_value=message),
        fetch_message=AsyncMock(return_value=message),
    )
    response = SimpleNamespace(defer_update=AsyncMock(), send_modal=AsyncMock())
    followup = SimpleNamespace(send=AsyncMock())
    client = SimpleNamespace(loop=loop)
    return SimpleNamespace(
        client=client,
        channel=channel,
        response=response,
        followup=followup,
        message=message,
        user=SimpleNamespace(id=555),
    )


def _flush(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


def _build_view(loop, controller, session, question, required, has_answer, optional):
    async def _inner():
        return srender.build_view(controller, session, question, required, has_answer, optional)

    return loop.run_until_complete(_inner())


def test_single_select_saves_and_gates(event_loop):
    controller = _build_controller(event_loop)
    interaction = _build_interaction(event_loop)
    session = Session(thread_id=interaction.channel.id, applicant_id=interaction.user.id)
    question = {
        "gid": "w_stage",
        "label": "Stage",
        "type": "single-select",
        "required": "TRUE",
        "values": "Beginner, Early Game, Mid Game, Late Game, End Game",
    }
    controller.renderer.get_question = lambda idx: question

    event_loop.run_until_complete(controller.sessions.save(session))
    event_loop.run_until_complete(controller.launch(interaction))
    _flush(event_loop)

    content, view = _build_view(event_loop, controller, session, question, True, False, False)
    next_button = next(child for child in view.children if getattr(child, "custom_id", "") == "nav_next")
    assert next_button.disabled is True

    event_loop.run_until_complete(
        controller._save_select_answer(interaction, session, question, "Mid Game")
    )
    _flush(event_loop)

    assert session.answers["w_stage"] == "Mid Game"

    content, view = _build_view(event_loop, controller, session, question, True, True, False)
    next_button = next(child for child in view.children if getattr(child, "custom_id", "") == "nav_next")
    assert next_button.disabled is False


def test_multi_select_saves_list_and_resumes(event_loop):
    controller = _build_controller(event_loop)
    interaction = _build_interaction(event_loop)
    session = Session(thread_id=interaction.channel.id, applicant_id=interaction.user.id)
    question = {
        "gid": "w_hydra_diff",
        "label": "Hydra",
        "type": "multi-select",
        "required": "FALSE",
        "values": "Normal, Hard, Brutal, Nightmare",
    }
    controller.renderer.get_question = lambda idx: question

    event_loop.run_until_complete(controller.sessions.save(session))
    event_loop.run_until_complete(controller.launch(interaction))
    _flush(event_loop)

    event_loop.run_until_complete(
        controller._save_multi_answer(interaction, session, question, ["Hard", "Brutal"])
    )
    _flush(event_loop)

    assert session.answers["w_hydra_diff"] == ["Hard", "Brutal"]

    _, view = _build_view(event_loop, controller, session, question, False, True, True)
    select = next(child for child in view.children if isinstance(child, discord.ui.Select))
    assert set(select.default_values) == {"Hard", "Brutal"}
