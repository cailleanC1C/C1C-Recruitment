import asyncio
import datetime as dt
import logging

import discord
from discord.ext import commands

from modules.onboarding.watcher_welcome import (
    TicketContext,
    WelcomeTicketWatcher,
    _NO_PLACEMENT_TAG,
    _determine_reservation_decision,
    build_closed_thread_name,
    parse_welcome_thread_name,
    rename_thread_to_reserved,
)
from shared.sheets import reservations as reservations_sheets


def _make_reservation(tag: str, *, created: dt.datetime | None = None) -> reservations_sheets.ReservationRow:
    created_at = created or dt.datetime.now(dt.timezone.utc)
    return reservations_sheets.ReservationRow(
        row_number=2,
        thread_id="123",
        ticket_user_id=111,
        recruiter_id=222,
        clan_tag=tag,
        reserved_until=None,
        created_at=created_at,
        status="active",
        notes="",
        username_snapshot="Tester",
        raw=[],
    )


def test_parse_thread_name_open() -> None:
    parts = parse_welcome_thread_name("W0298-Caillean AT")
    assert parts is not None
    assert parts.ticket_code == "W0298"
    assert parts.username == "Caillean AT"
    assert parts.state == "open"


def test_parse_thread_name_reserved() -> None:
    parts = parse_welcome_thread_name("Res-W0298-Caillean AT-C1CE")
    assert parts is not None
    assert parts.ticket_code == "W0298"
    assert parts.username == "Caillean AT"
    assert parts.clan_tag == "C1CE"
    assert parts.state == "reserved"


def test_parse_thread_name_closed() -> None:
    parts = parse_welcome_thread_name("Closed-W0298-Caillean AT-NONE")
    assert parts is not None
    assert parts.ticket_code == "W0298"
    assert parts.username == "Caillean AT"
    assert parts.clan_tag == "NONE"
    assert parts.state == "closed"


def test_decision_reservation_same_clan() -> None:
    row = _make_reservation("C1CE")
    decision = _determine_reservation_decision(
        "C1CE",
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "same"
    assert decision.status == "closed_same_clan"
    assert decision.open_deltas == {}
    assert decision.recompute_tags == ["C1CE"]


def test_decision_reservation_moved_clan() -> None:
    row = _make_reservation("C1CE")
    decision = _determine_reservation_decision(
        "VAGR",
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "other"
    assert decision.status == "closed_other_clan"
    assert decision.open_deltas == {"C1CE": 1, "VAGR": -1}
    assert set(decision.recompute_tags) == {"C1CE", "VAGR"}


def test_decision_no_reservation_final_real_clan() -> None:
    decision = _determine_reservation_decision(
        "C1CE",
        None,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "none_found"
    assert decision.status is None
    assert decision.open_deltas == {"C1CE": -1}
    assert decision.recompute_tags == ["C1CE"]


def test_decision_reservation_cancelled_with_no_clan() -> None:
    row = _make_reservation("MART")
    decision = _determine_reservation_decision(
        _NO_PLACEMENT_TAG,
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=False,
    )
    assert decision.label == "none"
    assert decision.status == "cancelled"
    assert decision.open_deltas == {"MART": 1}
    assert decision.recompute_tags == ["MART"]


def test_decision_no_reservation_no_clan() -> None:
    decision = _determine_reservation_decision(
        _NO_PLACEMENT_TAG,
        None,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=False,
    )
    assert decision.label == "none_found"
    assert decision.status is None
    assert decision.open_deltas == {}
    assert decision.recompute_tags == []


class _DummyMessage:
    def __init__(self, thread: "_DummyThread", message_id: int, content: str) -> None:
        self._thread = thread
        self.id = message_id
        self._content = content

    async def edit(self, *, content: str | None = None, view: object | None = None) -> None:
        if content is not None:
            self._thread.messages.append(content)


class _DummyThread:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.name: str | None = None
        self.guild = object()
        self._message_counter = 0

    async def send(self, content: str, **_: object) -> _DummyMessage:
        self.messages.append(content)
        self._message_counter += 1
        return _DummyMessage(self, self._message_counter, content)

    async def edit(self, *, name: str) -> None:
        self.name = name

    async def fetch_message(self, message_id: int) -> _DummyMessage:
        return _DummyMessage(self, message_id, f"fetched:{message_id}")


def test_handle_ticket_open_preserves_existing_values(monkeypatch) -> None:
    recorded: dict[str, list[str]] = {}

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_find(ticket: str):  # type: ignore[no-untyped-def]
        return 3, [ticket, "Old Tester", "MART", "2025-01-01 00:00:00"]

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        recorded["row"] = list(row)
        return "updated"

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.find_welcome_row",
        fake_find,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        context = TicketContext(thread_id=1, ticket_number="W0123", username="Tester")
        thread = _DummyThread()
        await watcher._handle_ticket_open(thread, context)
        await bot.close()

    asyncio.run(runner())

    row = recorded.get("row")
    assert row == ["W0123", "Tester", "MART", "2025-01-01 00:00:00"]


def test_finalize_skips_reservations_when_row_missing(monkeypatch, caplog) -> None:
    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "inserted"

    async def fail_async(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("should not be called when welcome row was missing")

    def fail_sync(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("should not be called when welcome row was missing")

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fail_async,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fail_async,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fail_async,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fail_async,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fail_sync,
    )

    caplog.set_level(logging.WARNING, logger="c1c.onboarding.welcome_watcher")

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", _NO_PLACEMENT_TAG]

        context = TicketContext(
            thread_id=1,
            ticket_number="W0123",
            username="Tester",
            recruit_id=111,
            recruit_display="Tester",
        )

        thread = _DummyThread()

        await watcher._finalize_clan_tag(
            thread,
            context,
            "C1CE",
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )

        await bot.close()

        assert context.state == "closed"
        assert context.reservation_label == "none_found"
        assert context.final_clan == "C1CE"
        assert thread.name == build_closed_thread_name("W0123", "Tester", "C1CE")
        assert thread.messages and "set clan tag" in thread.messages[-1]

    asyncio.run(runner())

    assert any("onboarding_row_missing" in record.message for record in caplog.records)


def test_finalize_no_reservation_consumes_open_spot(monkeypatch) -> None:
    adjustments: list[tuple[str, int]] = []
    recomputed: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "updated"

    async def fake_find_reservations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def fail_update(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("should not update reservation status when none exist")

    async def fake_adjust(tag: str, delta: int):
        adjustments.append((tag, delta))

    async def fake_recompute(tag: str, guild=None):  # type: ignore[no-untyped-def]
        recomputed.append(tag)

    def fake_find_clan(tag: str):  # type: ignore[no-untyped-def]
        return tag, ["", "", tag]

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fake_find_reservations,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fail_update,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fake_adjust,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fake_recompute,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fake_find_clan,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", _NO_PLACEMENT_TAG]
        context = TicketContext(thread_id=1, ticket_number="W0456", username="Tester")
        context.state = "awaiting_clan"
        thread = _DummyThread()
        await watcher._finalize_clan_tag(
            thread,
            context,
            "C1CE",
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )
        await bot.close()

    asyncio.run(runner())

    assert ("C1CE", -1) in adjustments
    assert "C1CE" in recomputed


def test_finalize_matching_reservation(monkeypatch) -> None:
    status_updates: list[tuple[int, str]] = []
    adjustments: list[tuple[str, int]] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "updated"

    async def fake_find_reservations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return [_make_reservation("C1CE")]

    async def fake_update(row_number: int, status: str):
        status_updates.append((row_number, status))

    async def fake_adjust(tag: str, delta: int):
        adjustments.append((tag, delta))

    async def fake_recompute(tag: str, guild=None):  # type: ignore[no-untyped-def]
        pass

    def fake_find_clan(tag: str):  # type: ignore[no-untyped-def]
        return tag, ["", "", tag]

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fake_find_reservations,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fake_update,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fake_adjust,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fake_recompute,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fake_find_clan,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", _NO_PLACEMENT_TAG]
        context = TicketContext(
            thread_id=1,
            ticket_number="W0007",
            username="Tester",
            recruit_id=111,
            recruit_display="Tester",
        )
        context.state = "awaiting_clan"
        thread = _DummyThread()
        await watcher._finalize_clan_tag(
            thread,
            context,
            "C1CE",
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )
        await bot.close()

        assert context.reservation_label == "same"

    asyncio.run(runner())

    assert adjustments == []
    assert status_updates == [(2, "closed_same_clan")]


def test_finalize_moved_reservation(monkeypatch) -> None:
    adjustments: list[tuple[str, int]] = []
    status_updates: list[tuple[int, str]] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "updated"

    async def fake_find_reservations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return [_make_reservation("MART")]

    async def fake_update(row_number: int, status: str):
        status_updates.append((row_number, status))

    async def fake_adjust(tag: str, delta: int):
        adjustments.append((tag, delta))

    async def fake_recompute(tag: str, guild=None):  # type: ignore[no-untyped-def]
        pass

    def fake_find_clan(tag: str):  # type: ignore[no-untyped-def]
        return tag, ["", "", tag]

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fake_find_reservations,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fake_update,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fake_adjust,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fake_recompute,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fake_find_clan,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", "MART", "VAGR", _NO_PLACEMENT_TAG]
        context = TicketContext(
            thread_id=1,
            ticket_number="W0008",
            username="Tester",
            recruit_id=111,
            recruit_display="Tester",
        )
        context.state = "awaiting_clan"
        thread = _DummyThread()
        await watcher._finalize_clan_tag(
            thread,
            context,
            "VAGR",
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )
        await bot.close()

        assert context.reservation_label == "other"

    asyncio.run(runner())

    assert ("MART", 1) in adjustments
    assert ("VAGR", -1) in adjustments
    assert status_updates == [(2, "closed_other_clan")]


def test_finalize_none_tag_cancels_reservation(monkeypatch) -> None:
    adjustments: list[tuple[str, int]] = []
    status_updates: list[tuple[int, str]] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "updated"

    async def fake_find_reservations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return [_make_reservation("MART")]

    async def fake_update(row_number: int, status: str):
        status_updates.append((row_number, status))

    async def fake_adjust(tag: str, delta: int):
        adjustments.append((tag, delta))

    async def fake_recompute(tag: str, guild=None):  # type: ignore[no-untyped-def]
        pass

    def fail_find_clan(tag: str):  # type: ignore[no-untyped-def]
        raise AssertionError("should not look up clan row for NONE")

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fake_find_reservations,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fake_update,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fake_adjust,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fake_recompute,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fail_find_clan,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["MART", _NO_PLACEMENT_TAG]
        context = TicketContext(
            thread_id=1,
            ticket_number="W0009",
            username="Tester",
            recruit_id=111,
            recruit_display="Tester",
        )
        context.state = "awaiting_clan"
        thread = _DummyThread()
        await watcher._finalize_clan_tag(
            thread,
            context,
            _NO_PLACEMENT_TAG,
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )
        await bot.close()

        assert context.reservation_label == "none"

    asyncio.run(runner())

    assert adjustments == [("MART", 1)]
    assert status_updates == [(2, "cancelled")]


def test_finalize_none_tag_without_reservation(monkeypatch) -> None:
    adjustments: list[tuple[str, int]] = []
    status_updates: list[tuple[int, str]] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        return "updated"

    async def fake_find_reservations(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def fake_update(row_number: int, status: str):
        status_updates.append((row_number, status))

    async def fake_adjust(tag: str, delta: int):
        adjustments.append((tag, delta))

    recomputed: list[str] = []

    async def fake_recompute(tag: str, guild=None):  # type: ignore[no-untyped-def]
        recomputed.append(tag)

    def fail_find_clan(tag: str):  # type: ignore[no-untyped-def]
        raise AssertionError("should not look up clan row for NONE")

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.find_active_reservations_for_recruit",
        fake_find_reservations,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.reservations_sheets.update_reservation_status",
        fake_update,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.adjust_manual_open_spots",
        fake_adjust,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.availability.recompute_clan_availability",
        fake_recompute,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.recruitment_sheets.find_clan_row",
        fail_find_clan,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["MART", _NO_PLACEMENT_TAG]
        context = TicketContext(
            thread_id=1,
            ticket_number="W0010",
            username="Tester",
            recruit_id=222,
            recruit_display="Tester",
        )
        context.state = "awaiting_clan"
        thread = _DummyThread()
        await watcher._finalize_clan_tag(
            thread,
            context,
            _NO_PLACEMENT_TAG,
            actor=None,
            source="test",
            prompt_message=None,
            view=None,
        )
        await bot.close()

        assert context.reservation_label == "none_found"

    asyncio.run(runner())

    assert adjustments == []
    assert status_updates == []
    assert recomputed == []


def test_manual_close_missing_row_prompts(monkeypatch, caplog) -> None:
    inserted_rows: list[list[str]] = []

    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_find_row(ticket: str):  # type: ignore[no-untyped-def]
        return None

    def fake_upsert(row, headers):  # type: ignore[no-untyped-def]
        inserted_rows.append(list(row))
        return "inserted"

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.find_welcome_row",
        fake_find_row,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fake_upsert,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", _NO_PLACEMENT_TAG]
        context = TicketContext(thread_id=1, ticket_number="W0500", username="Tester")
        thread = _DummyThread()
        caplog.set_level(logging.WARNING, logger="c1c.onboarding.welcome_watcher")
        await watcher._handle_manual_close(
            thread,
            context,
            reason="manual_close_without_ticket_tool",
        )
        await bot.close()

        assert context.state == "awaiting_clan"
        assert context.row_created_during_close is True
        assert thread.messages and "Which clan tag" in thread.messages[0]

    asyncio.run(runner())

    assert inserted_rows and inserted_rows[0][:2] == ["W0500", "Tester"]
    assert any("onboarding_row_missing_manual_close" in record.message for record in caplog.records)


def test_manual_close_existing_clan_skips_prompt(monkeypatch) -> None:
    async def fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    def fake_find_row(ticket: str):  # type: ignore[no-untyped-def]
        return 5, [ticket, "Tester", "C1CE", "2025-01-01 00:00:00"]

    def fail_upsert(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("should not upsert when row exists with clan")

    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.find_welcome_row",
        fake_find_row,
    )
    monkeypatch.setattr(
        "modules.onboarding.watcher_welcome.onboarding_sheets.upsert_welcome",
        fail_upsert,
    )

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        watcher = WelcomeTicketWatcher(bot)
        watcher._clan_tags = ["C1CE", _NO_PLACEMENT_TAG]
        context = TicketContext(thread_id=1, ticket_number="W0501", username="Tester")
        thread = _DummyThread()
        await watcher._handle_manual_close(
            thread,
            context,
            reason="manual_close_without_ticket_tool",
        )
        await bot.close()

        assert context.state == "open"
        assert not thread.messages

    asyncio.run(runner())


class _RenameThread:
    def __init__(self, name: str) -> None:
        self.name = name
        self.id = 123
        self.renames: list[str] = []

    async def edit(self, *, name: str) -> None:
        self.name = name
        self.renames.append(name)


def test_rename_thread_to_reserved_success() -> None:
    thread = _RenameThread("W0999-Tester")

    async def runner() -> None:
        await rename_thread_to_reserved(thread, "C1CE")

    asyncio.run(runner())

    assert thread.name == "Res-W0999-Tester-C1CE"
    assert thread.renames == ["Res-W0999-Tester-C1CE"]
