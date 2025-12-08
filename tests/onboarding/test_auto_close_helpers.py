import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from modules.onboarding.watcher_promo import PromoTicketContext, PromoTicketWatcher
from modules.onboarding.watcher_welcome import (
    TicketContext,
    WelcomeTicketWatcher,
    _NO_PLACEMENT_TAG,
)


def test_welcome_auto_close_helper_avoids_picker_and_uses_sheet():
    watcher = WelcomeTicketWatcher(bot=SimpleNamespace())
    context = TicketContext(thread_id=123, ticket_number="W0001", username="tester")

    edit_calls = []

    async def fake_edit(**kwargs):
        assert context.thread_id in watcher._auto_closed_threads
        edit_calls.append(kwargs)

    thread = SimpleNamespace(id=123, name="W0001-tester")
    thread.edit = AsyncMock(side_effect=fake_edit)
    thread.send = AsyncMock(side_effect=lambda *_args, **_kwargs: assert_thread_marked(watcher, context))

    def assert_thread_marked(current_watcher: WelcomeTicketWatcher, current_context: TicketContext):
        assert current_context.thread_id in current_watcher._auto_closed_threads

    async def fake_finalize(thread_arg, context_arg, final_tag, **kwargs):
        assert final_tag == _NO_PLACEMENT_TAG
        context_arg.state = "closed"

    watcher._finalize_clan_tag = AsyncMock(side_effect=fake_finalize)

    asyncio.run(
        watcher.auto_close_for_inactivity(
            thread,
            context,
            notice="inactivity notice",
            closed_name="W0001-tester-NONE",
            final_tag=_NO_PLACEMENT_TAG,
        )
    )

    watcher._finalize_clan_tag.assert_awaited_once()
    assert context.prompt_message_id is None
    assert context.state == "closed"
    assert edit_calls, "thread edits should be attempted during auto-close"


def test_promo_auto_close_helper_uses_sheet_without_picker():
    watcher = PromoTicketWatcher(bot=SimpleNamespace())
    context = PromoTicketContext(
        thread_id=456,
        ticket_number="M0002",
        username="applicant",
        promo_type="move",
        thread_created="2025-01-01",
        year="2025",
        month="January",
    )

    edit_calls = []

    async def fake_edit(**kwargs):
        assert context.thread_id in watcher._auto_closed_threads
        edit_calls.append(kwargs)

    thread = SimpleNamespace(id=456, name="M0002-applicant")
    thread.edit = AsyncMock(side_effect=fake_edit)
    thread.send = AsyncMock(side_effect=lambda *_args, **_kwargs: None)

    watcher._complete_close = AsyncMock()

    asyncio.run(
        watcher.auto_close_for_inactivity(
            thread,
            context,
            notice="promo inactivity",
            closed_name="M0002-applicant-NONE",
        )
    )

    watcher._complete_close.assert_awaited_once()
    assert context.prompt_message_id is None
    assert edit_calls, "thread edits should be attempted during promo auto-close"
