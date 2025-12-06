import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from modules.onboarding import sessions
from modules.onboarding.controllers.welcome_controller import WelcomeController
from modules.onboarding.sessions import ensure_session_for_thread
from modules.onboarding.watcher_promo import PromoTicketWatcher
from modules.onboarding.watcher_welcome import WelcomeTicketWatcher, TicketContext, _process_incomplete_thread


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.bot = False


class _DummyMessage:
    def __init__(self, user_id: int, mentions: bool | list[_DummyUser] = True):
        self.id = 555
        self.author = _DummyUser(user_id)
        if mentions is False:
            self.mentions: list[_DummyUser] = []
        elif isinstance(mentions, list):
            self.mentions = mentions
        else:
            self.mentions = [_DummyUser(user_id)]


class _DummyThread:
    def __init__(self, thread_id: int, name: str, created_at: datetime):
        self.id = thread_id
        self.name = name
        self.created_at = created_at


class _DummyBot:
    pass


@pytest.fixture()
def memory_sheet(monkeypatch):
    rows: dict[tuple[int, int], dict] = {}
    onboarding_rows: dict[str, dict] = {}

    def fake_load(user_id: int, thread_id: int):
        key = (int(user_id), int(thread_id))
        return rows.get(key)

    def fake_save(payload: dict, allow_create: bool = True):
        try:
            key = (int(payload.get("user_id") or 0), int(payload.get("thread_id") or 0))
        except Exception:
            key = (payload.get("user_id"), payload.get("thread_id"))
        rows[key] = payload
        return True

    fake_sheet_module = type("_FakeSheet", (), {"load": staticmethod(fake_load), "save": staticmethod(fake_save)})
    monkeypatch.setattr(sessions, "sess_sheet", fake_sheet_module)
    monkeypatch.setattr(
        "shared.sheets.onboarding_sessions.upsert_session",
        lambda **payload: onboarding_rows.setdefault(str(payload.get("thread_id", "")), payload),
    )
    monkeypatch.setattr("shared.sheets.onboarding_sessions.load", lambda *_: None)
    monkeypatch.setattr("shared.sheets.onboarding_sessions.load_all", lambda: list(onboarding_rows.values()))
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.append_onboarding_session_row",
        lambda **_: "inserted",
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_promo.onboarding_sheets.append_onboarding_session_row",
        lambda **_: "inserted",
    )
    return rows


@pytest.fixture(autouse=True)
def _clear_target_cache(monkeypatch):
    from modules.onboarding import watcher_welcome

    watcher_welcome._TARGET_CACHE.clear()


def _install_message_fixtures(
    monkeypatch, module, user_id: int = 42, message: _DummyMessage | None = None
):
    dummy_message = message or _DummyMessage(user_id)

    async def _locate(_thread):
        return dummy_message

    monkeypatch.setattr(module, "locate_welcome_message", _locate)


def _extract_target(message):
    target = message.mentions[0] if getattr(message, "mentions", None) else getattr(message, "author", None)
    return (target.id if target else None, getattr(message, "id", None))


def test_welcome_thread_open_creates_session(memory_sheet, monkeypatch):
    created_at = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    thread = _DummyThread(101, "W1234-user", created_at)
    context = TicketContext(thread_id=thread.id, ticket_number="W1234", username="user")

    _install_message_fixtures(monkeypatch, __import__("modules.onboarding.watcher_welcome", fromlist=["locate_welcome_message"]))
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.extract_target_from_message",
        _extract_target,
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.upsert_welcome",
        lambda row, headers: "inserted",
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.find_welcome_row",
        lambda ticket: None,
    )
    monkeypatch.setattr(
        "modules.common.feature_flags.is_enabled",
        lambda flag: True,
    )

    watcher = WelcomeTicketWatcher(bot=_DummyBot())
    asyncio.run(watcher._handle_ticket_open(thread, context))

    assert (42, 101) in memory_sheet
    payload = memory_sheet[(42, 101)]
    assert payload.get("completed") is False
    assert payload.get("answers") == {}
    assert payload.get("updated_at") == created_at.isoformat()


def test_welcome_ticket_open_falls_back_to_author_when_no_mentions(memory_sheet, monkeypatch):
    created_at = datetime(2025, 2, 2, 12, 0, tzinfo=timezone.utc)
    thread = _DummyThread(505, "W5678-user", created_at)
    context = TicketContext(thread_id=thread.id, ticket_number="W5678", username="user")

    dummy_message = _DummyMessage(99, mentions=False)
    _install_message_fixtures(
        monkeypatch,
        __import__("modules.onboarding.watcher_welcome", fromlist=["locate_welcome_message"]),
        message=dummy_message,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.extract_target_from_message",
        _extract_target,
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.upsert_welcome",
        lambda row, headers: "inserted",
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.find_welcome_row",
        lambda ticket: None,
    )
    monkeypatch.setattr(
        "modules.common.feature_flags.is_enabled",
        lambda flag: True,
    )

    watcher = WelcomeTicketWatcher(bot=_DummyBot())
    asyncio.run(watcher._handle_ticket_open(thread, context))

    assert (99, 505) in memory_sheet
    payload = memory_sheet[(99, 505)]
    assert payload.get("completed") is False
    assert payload.get("answers") == {}
    assert payload.get("updated_at") == created_at.isoformat()


def test_promo_thread_open_creates_session(memory_sheet, monkeypatch):
    created_at = datetime(2025, 1, 3, 9, 30, tzinfo=timezone.utc)
    thread = _DummyThread(202, "R1234-player", created_at)

    _install_message_fixtures(monkeypatch, __import__("modules.onboarding.watcher_promo", fromlist=["locate_welcome_message"]))
    monkeypatch.setattr(
        "modules.onboarding.watcher_promo.extract_target_from_message",
        _extract_target,
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.upsert_promo",
        lambda row, headers: "inserted",
    )
    monkeypatch.setattr(
        "shared.sheets.onboarding.find_promo_row",
        lambda ticket: None,
    )
    monkeypatch.setattr(
        "modules.common.feature_flags.is_enabled",
        lambda flag: True,
    )

    watcher = PromoTicketWatcher(bot=_DummyBot())
    asyncio.run(watcher.on_thread_create(thread))

    assert (42, 202) in memory_sheet
    payload = memory_sheet[(42, 202)]
    assert payload.get("completed") is False
    assert payload.get("panel_message_id") == 0
    assert payload.get("updated_at") == created_at.isoformat()


def test_panel_start_updates_existing_session(memory_sheet, monkeypatch):
    thread_id = 303
    user_id = 77
    created_at = datetime(2025, 1, 4, 8, 0, tzinfo=timezone.utc)
    panel_time = created_at + timedelta(minutes=10)

    asyncio.run(ensure_session_for_thread(user_id, thread_id, updated_at=created_at))

    controller = WelcomeController(bot=_DummyBot())
    monkeypatch.setattr(controller, "_resolve_applicant_id", lambda *_: user_id)

    asyncio.run(
        controller._persist_session_start(
            thread_id,
            panel_message_id=999,
            session_data=None,
            panel_created_at=panel_time,
        )
    )

    payload = memory_sheet[(user_id, thread_id)]
    assert payload.get("panel_message_id") == 999
    assert payload.get("updated_at") == panel_time.isoformat()
    assert payload.get("step_index") == 0


def test_inactivity_scan_creates_session_row(memory_sheet, monkeypatch):
    now = datetime(2025, 1, 5, 10, 0, tzinfo=timezone.utc)
    created_at = now
    thread = _DummyThread(404, "W1234-empty", created_at)

    _install_message_fixtures(monkeypatch, __import__("modules.onboarding.watcher_welcome", fromlist=["locate_welcome_message"]))
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.extract_target_from_message",
        _extract_target,
    )

    asyncio.run(_process_incomplete_thread(bot=_DummyBot(), thread=thread, now=now))

    assert (42, 404) in memory_sheet
    payload = memory_sheet[(42, 404)]
    assert payload.get("completed") is False
    assert payload.get("updated_at") == created_at.isoformat()
