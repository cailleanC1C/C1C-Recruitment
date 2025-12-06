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
    thread = SimpleNamespace(
        id=111,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        name="W0600-smurf",
    )
    context = TicketContext(thread_id=111, ticket_number="W0600", username="smurf")

    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "find_welcome_row", lambda ticket: None)
    monkeypatch.setattr(watcher_welcome, "locate_welcome_message", AsyncMock(return_value=object()))
    monkeypatch.setattr(watcher_welcome, "extract_target_from_message", lambda _: (222, None))
    monkeypatch.setattr(watcher_welcome, "ensure_session_for_thread", AsyncMock())

    welcome_calls = []
    session_calls = []
    session_sheet_rows = []

    def fake_append_welcome(ticket, username, clan_tag, date_closed):
        welcome_calls.append((ticket, username, clan_tag, date_closed))
        return "inserted"

    def fake_append_session(**kwargs):
        session_calls.append(kwargs)
        return "inserted"

    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "append_welcome_ticket_row", fake_append_welcome)
    monkeypatch.setattr(watcher_welcome.onboarding_sheets, "append_onboarding_session_row", fake_append_session)
    monkeypatch.setattr(watcher_welcome.onboarding_sessions, "save", lambda payload: session_sheet_rows.append(payload))

    asyncio.run(watcher._handle_ticket_open(thread, context))

    assert welcome_calls == [("W0600", "smurf", "", "")]
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
    assert session_sheet_rows[0]["thread_id"] == str(thread.id)
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
    session_calls = []
    session_sheet_rows = []

    def fake_append_promo(*args, **kwargs):
        promo_calls.append(args)
        return "inserted"

    def fake_append_session(**kwargs):
        session_calls.append(kwargs)
        return "inserted"

    monkeypatch.setattr(watcher_promo.onboarding_sheets, "append_promo_ticket_row", fake_append_promo)
    monkeypatch.setattr(watcher_promo.onboarding_sheets, "append_onboarding_session_row", fake_append_session)
    monkeypatch.setattr(watcher_promo.onboarding_sessions, "save", lambda payload: session_sheet_rows.append(payload))

    asyncio.run(watcher.on_thread_create(thread))

    assert promo_calls == [
        (
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
    ]
    assert session_calls[0]["flow"] == "promo"
    assert session_calls[0]["status"] == "open"
    assert session_calls[0]["ticket"] == "M0011"
    assert session_calls[0]["thread_id"] == 222
    assert session_calls[0]["user_id"] == 333
    assert session_calls[0]["created_at"] == thread.created_at
    assert session_sheet_rows[0]["thread_name"] == thread.name


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

    assert any("result=error" in record.message for record in caplog.records)
