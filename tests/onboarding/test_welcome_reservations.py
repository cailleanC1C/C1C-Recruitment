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
    assert decision.label == "moved"
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
    assert decision.label == "none"
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
    assert decision.label == "cancelled"
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
    assert decision.label == "none"
    assert decision.status is None
    assert decision.open_deltas == {}
    assert decision.recompute_tags == []


class _DummyThread:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.name: str | None = None
        self.guild = object()

    async def send(self, content: str, **_: object) -> None:
        self.messages.append(content)

    async def edit(self, *, name: str) -> None:
        self.name = name

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
            ticket_number="0123",
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
        assert context.reservation_label == "none"
        assert context.final_clan == "C1CE"
        assert thread.name == "Closed-0123-Tester-C1CE"
        assert thread.messages and "set clan tag" in thread.messages[-1]

    asyncio.run(runner())

    assert any("onboarding_row_missing" in record.message for record in caplog.records)
