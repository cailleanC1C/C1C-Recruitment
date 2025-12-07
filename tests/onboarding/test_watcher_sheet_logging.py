import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from modules.onboarding import watcher_promo
from modules.onboarding import watcher_welcome
from modules.onboarding.watcher_promo import PromoTicketWatcher
from modules.onboarding.watcher_welcome import TicketContext, WelcomeTicketWatcher


def test_welcome_ticket_logs_sheets(monkeypatch):
    watcher = WelcomeTicketWatcher(bot=MagicMock())
    watcher.bot.user = SimpleNamespace(id=999, bot=True)
    thread = SimpleNamespace(
        id=111,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        name="W0600-smurf",
    )
    context = TicketContext(thread_id=111, ticket_number="W0600", username="smurf")

    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "find_welcome_row", lambda ticket: None)
    starter = SimpleNamespace(
        mentions=[SimpleNamespace(id=222, bot=False)],
        content="<@222>",
        author=SimpleNamespace(id=watcher.bot.user.id, bot=True),
    )
    monkeypatch.setattr(watcher_welcome, "locate_welcome_message", AsyncMock(return_value=starter))
    monkeypatch.setattr(watcher_welcome, "ensure_session_for_thread", AsyncMock())

    welcome_calls = []
    session_calls = []
    session_sheet_rows = []

    def fake_append_welcome(ticket, username, clan_tag, date_closed, **kwargs):
        welcome_calls.append((ticket, username, clan_tag, date_closed, kwargs))
        return "inserted"

    def fake_append_session(**kwargs):
        session_calls.append(kwargs)
        return "inserted"

    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "append_welcome_ticket_row", fake_append_welcome)
    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "append_onboarding_session_row", fake_append_session)
    monkeypatch.setattr(
        watcher_welcome.onboarding_sessions,
        "upsert_session",
        lambda **payload: session_sheet_rows.append(payload),
    )

    asyncio.run(watcher._handle_ticket_open(thread, context))

    assert welcome_calls[0][:4] == ("W0600", "smurf", "", "")
    assert welcome_calls[0][4]["user_id"] == 222
    assert welcome_calls[0][4]["thread_id"] == thread.id
    assert welcome_calls[0][4]["created_at"] == thread.created_at
    assert session_calls == [
        {
            "ticket": "W0600",
            "thread_id": 111,
            "user_id": 222,
            "flow": "welcome",
            "status": "open",
            "created_at": thread.created_at,
        }
    ]
    assert session_calls[0]["created_at"] == thread.created_at
    assert session_sheet_rows[0]["thread_id"] == thread.id
    assert session_sheet_rows[0]["thread_name"] == thread.name


def test_promo_ticket_logs_sheets(monkeypatch):
    watcher = PromoTicketWatcher(bot=MagicMock())
    watcher._features_enabled = lambda: True  # type: ignore[attr-defined]
    watcher._is_ticket_thread = lambda thread: True  # type: ignore[attr-defined]
    thread = SimpleNamespace(id=222, created_at=datetime(2025, 2, 2, tzinfo=timezone.utc), name="M0011-user")
    context = watcher_promo.PromoTicketContext(
        thread_id=222,
        ticket_number="M0011",
        username="caillean",
        promo_type="move",
        thread_created="2025-02-02",
        year="2025",
        month="February",
    )

    monkeypatch.setattr(watcher_promo.onboarding_sheets, "find_promo_row", lambda ticket: None)
    monkeypatch.setattr(watcher_promo, "locate_welcome_message", AsyncMock(return_value=object()))
    monkeypatch.setattr(watcher_promo, "extract_target_from_message", lambda _: (333, None))
    monkeypatch.setattr(watcher_promo, "ensure_session_for_thread", AsyncMock())

    promo_calls = []

    def fake_append_promo(*args, **kwargs):
        promo_calls.append((args, kwargs))
        return "inserted"

    monkeypatch.setattr(watcher_promo.onboarding_sheets, "append_promo_ticket_row", fake_append_promo)
    monkeypatch.setattr(watcher_promo.onboarding_sheets, "append_onboarding_session_row", AsyncMock())

    asyncio.run(watcher.on_thread_create(thread))

    # Closing the ticket should not append another ticket row.
    asyncio.run(watcher._ensure_row_initialized(thread, context))

    args, kwargs = promo_calls[0]
    assert args == (
        "M0011",
        "user",
        "",
        "player move request",
        "2025-02-02 00:00:00",
        "2025",
        "February",
        "",
        "",
        "",
    )
    assert kwargs["user_id"] == 333
    assert kwargs["thread_id"] == thread.id
    assert kwargs["created_at"] == thread.created_at
    assert len(promo_calls) == 1
    # No onboarding session rows are created until the promo panel is posted.
    assert watcher_promo.onboarding_sheets.append_onboarding_session_row.await_count == 0


def test_promo_ticket_open_logs_error_on_failure(monkeypatch, caplog):
    watcher = PromoTicketWatcher(bot=MagicMock())
    thread = SimpleNamespace(id=333, created_at=datetime(2025, 3, 3, tzinfo=timezone.utc))
    context = watcher_promo.PromoTicketContext(
        thread_id=333,
        ticket_number="L0001",
        username="tester",
        promo_type="lead",
        thread_created="2025-03-03",
        year="2025",
        month="March",
    )

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(watcher_promo.onboarding_sheets, "append_promo_ticket_row", boom)

    with caplog.at_level("ERROR"):
        asyncio.run(watcher._log_ticket_open(thread, context))

    assert any("result=error" in str(record.msg) for record in caplog.records)
