import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.onboarding.ui.panels import WelcomePanel


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
    response = SimpleNamespace(defer_update=AsyncMock())
    followup = SimpleNamespace(send=AsyncMock())
    message = MagicMock()
    message.id = 424242
    message.edit = AsyncMock()
    client = SimpleNamespace(loop=event_loop)
    return SimpleNamespace(
        client=client,
        response=response,
        followup=followup,
        message=message,
        channel=None,
        user=SimpleNamespace(id=111, display_name="Recruit"),
    )


@pytest.fixture
def controller():
    async def _launch(interaction):
        await interaction.message.edit()

    async def _restart(interaction):
        await interaction.message.edit()

    controller = SimpleNamespace(
        launch=AsyncMock(side_effect=_launch),
        restart=AsyncMock(side_effect=_restart),
        log=MagicMock(),
    )
    return controller


@pytest.fixture
def view(controller, event_loop):
    created_view: WelcomePanel | None = None

    async def _build() -> None:
        nonlocal created_view
        created_view = WelcomePanel(controller)

    event_loop.run_until_complete(_build())
    assert created_view is not None
    return created_view


def _open_button(view: WelcomePanel):
    for child in view.children:
        if getattr(child, "custom_id", None) == "open_questions":
            return child
    raise AssertionError("open questions button not found")


def _restart_button(view: WelcomePanel):
    for child in view.children:
        if getattr(child, "custom_id", None) == "restart_wizard":
            return child
    raise AssertionError("restart button not found")


def test_open_questions_edits_panel_in_place(interaction, controller, view):
    button = _open_button(view)
    loop = interaction.client.loop
    loop.run_until_complete(button.callback(interaction))
    loop.run_until_complete(asyncio.sleep(0))

    controller.launch.assert_awaited_once_with(interaction)
    interaction.response.defer_update.assert_awaited_once()
    assert interaction.followup.send.await_count == 0
    interaction.message.edit.assert_awaited_once()


def test_restart_edits_panel_in_place(interaction, controller, view):
    open_button = _open_button(view)
    restart_button = _restart_button(view)
    loop = interaction.client.loop

    loop.run_until_complete(open_button.callback(interaction))
    loop.run_until_complete(restart_button.callback(interaction))
    loop.run_until_complete(asyncio.sleep(0))

    assert interaction.followup.send.await_count == 0
    assert interaction.message.edit.await_count >= 2
    controller.restart.assert_awaited_once_with(interaction)


def test_single_message_policy_no_followups(interaction, controller, view):
    button = _open_button(view)
    loop = interaction.client.loop

    loop.run_until_complete(button.callback(interaction))
    loop.run_until_complete(button.callback(interaction))
    loop.run_until_complete(asyncio.sleep(0))

    assert interaction.followup.send.await_count == 0
    assert interaction.message.edit.await_count >= 1
    assert controller.launch.await_count == 2
