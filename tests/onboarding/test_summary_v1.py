import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, ANY

import discord
import pytest

from modules.onboarding.controllers.wizard import WizardController
from modules.onboarding.sessions import Session, SessionStore
from modules.onboarding.ui import render_summary


class _Renderer:
    def __init__(self) -> None:
        self.questions: list[dict] = []

    def render(self, session: Session):
        return ("legacy", discord.ui.View())

    def get_question(self, index: int) -> dict:
        return self.questions[index]

    def all_questions(self) -> list[dict]:
        return list(self.questions)


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
    message.id = 777
    message.edit = AsyncMock()
    channel = SimpleNamespace(
        id=4321,
        send=AsyncMock(return_value=message),
        fetch_message=AsyncMock(return_value=message),
    )
    response = SimpleNamespace(defer_update=AsyncMock(), send_modal=AsyncMock())
    followup = SimpleNamespace(send=AsyncMock())
    client = SimpleNamespace(loop=event_loop)
    return SimpleNamespace(
        client=client,
        channel=channel,
        response=response,
        followup=followup,
        message=message,
        user=SimpleNamespace(id=2468),
    )


@pytest.fixture
def controller(event_loop):
    class _Bot:
        def __init__(self, loop):
            self.loop = loop
            self.logger = MagicMock()

    bot = _Bot(event_loop)
    sessions = SessionStore()
    renderer = _Renderer()
    ctrl = WizardController(bot, sessions, renderer)
    return ctrl


@pytest.fixture
def session_factory():
    def _build(thread_id: int = 4321, applicant_id: int = 2468) -> Session:
        return Session(thread_id=thread_id, applicant_id=applicant_id)

    return _build


def _flush(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


def test_finish_creates_embed_and_marks_complete(event_loop, interaction, controller, session_factory):
    session = session_factory()
    controller.renderer.questions = [
        {"gid": "w_ign", "label": "IGN", "type": "short"},
        {"gid": "w_play", "label": "Playstyle", "type": "paragraph"},
    ]
    controller.config.recruiter_role_id = 999
    controller.config.ping_recruiter = True

    session.answers = {"w_ign": "Caillean", "w_play": "Focused but chill"}

    event_loop.run_until_complete(controller.sessions.save(session))
    event_loop.run_until_complete(controller.finish(interaction, session))
    _flush(event_loop)

    assert session.completed is True
    assert session.completed_at is not None

    interaction.channel.send.assert_awaited_once_with(
        content="<@&999> New onboarding submission ready.",
        embed=ANY,
    )
    embed_arg = interaction.channel.send.await_args.kwargs["embed"]
    assert embed_arg.title == "🎉 Welcome Summary"
    assert embed_arg.fields[0].name == "**IGN**"
    assert embed_arg.fields[0].value == "Caillean"
    assert embed_arg.fields[1].value == "Focused but chill"
    interaction.followup.send.assert_awaited_with(
        "✅ All done — recruiter will review soon.",
        ephemeral=True,
    )


def test_paragraphs_enforce_length_cap(session_factory):
    session = session_factory()
    session.answers = {"w_play": "x" * 400}
    session.mark_completed()

    questions = [{"gid": "w_play", "label": "Playstyle", "type": "paragraph"}]
    embed, answered = render_summary.build_summary_embed(session, questions)

    assert answered == 1
    assert len(embed.fields) == 1
    assert len(embed.fields[0].value) == 300
    assert "🕓 Completed" in embed.footer.text
