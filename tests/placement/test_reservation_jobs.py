import asyncio
import datetime as dt
from types import SimpleNamespace

from modules.placement import reservation_jobs
from shared.sheets import reservations


class FakeChannel:
    def __init__(self, channel_id: int, *, guild: object | None = None) -> None:
        self.id = channel_id
        self.guild = guild or SimpleNamespace(id=1234)
        self.sent: list[str] = []

    async def send(self, *, content: str | None = None, **_: object) -> None:
        if content is not None:
            self.sent.append(content)


class FakeBot:
    def __init__(self, channels: dict[int, FakeChannel]) -> None:
        self._channels = dict(channels)

    async def wait_until_ready(self) -> None:
        return None

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id: int):
        return self._channels.get(channel_id)


def _reservation_row(
    *,
    row_number: int,
    clan_tag: str,
    reserved_until: dt.date | None,
    status: str = "active",
    thread_id: int = 1000,
    ticket_user_id: int | None = 2000,
    ticket_username: str = "Recruit One",
) -> reservations.ReservationRow:
    return reservations.ReservationRow(
        row_number=row_number,
        thread_id=str(thread_id),
        ticket_user_id=ticket_user_id,
        recruiter_id=3000,
        clan_tag=clan_tag,
        reserved_until=reserved_until,
        created_at=None,
        status=status,
        notes="",
        ticket_username=ticket_username,
        raw=[str(thread_id), str(ticket_user_id or ""), "3000", clan_tag, "", "", status, "", ticket_username],
    )


def test_reservations_reminder_daily_posts_message(monkeypatch):
    today = dt.date(2025, 1, 10)
    due_row = _reservation_row(row_number=2, clan_tag="#AAA", reserved_until=today, thread_id=5555)
    future_row = _reservation_row(
        row_number=3,
        clan_tag="#BBB",
        reserved_until=today + dt.timedelta(days=1),
        thread_id=6666,
    )

    ledger = reservations.ReservationLedger(rows=[due_row, future_row], header_index={"status": 6})

    async def fake_load():
        return ledger

    recomputed: list[tuple[str, object | None]] = []

    async def fake_recompute(clan_tag: str, *, guild=None):
        recomputed.append((clan_tag, guild))

    fake_thread = FakeChannel(5555)
    bot = FakeBot({5555: fake_thread})

    monkeypatch.setattr(reservation_jobs, "_reservations_enabled", lambda: True)
    monkeypatch.setattr(reservation_jobs.reservations, "load_reservation_ledger", fake_load)
    monkeypatch.setattr(reservation_jobs.availability, "recompute_clan_availability", fake_recompute)
    monkeypatch.setattr(reservation_jobs, "get_recruiter_role_ids", lambda: {42})

    asyncio.run(reservation_jobs.reservations_reminder_daily(bot=bot, today=today))

    assert len(fake_thread.sent) == 1
    content = fake_thread.sent[0]
    lines = content.splitlines()
    assert lines[0] == "<@&42>"
    assert "reserved spot" in lines[1]
    assert "extend the reservation" in content

    assert recomputed == [("AAA", fake_thread.guild)]


def test_reservations_autorelease_daily_expires_overdue(monkeypatch):
    today = dt.date(2025, 1, 12)
    due_row = _reservation_row(row_number=2, clan_tag="#AAA", reserved_until=today, thread_id=7777)
    future_row = _reservation_row(
        row_number=3,
        clan_tag="#AAA",
        reserved_until=today + dt.timedelta(days=2),
        thread_id=8888,
    )
    inactive_row = _reservation_row(
        row_number=4,
        clan_tag="#CCC",
        reserved_until=today - dt.timedelta(days=1),
        status="expired",
        thread_id=9999,
    )

    ledger = reservations.ReservationLedger(
        rows=[due_row, future_row, inactive_row],
        header_index={"status": 6},
    )

    async def fake_load():
        return ledger

    updates: list[tuple[int, str, int | None]] = []

    async def fake_update(row_number: int, status: str, *, status_column: int | None = None):
        updates.append((row_number, status, status_column))

    recomputed: list[str] = []

    async def fake_recompute(clan_tag: str, *, guild=None):
        recomputed.append(clan_tag)

    summary_thread = FakeChannel(4444)
    fake_thread = FakeChannel(7777)
    bot = FakeBot({7777: fake_thread, 4444: summary_thread})

    monkeypatch.setattr(reservation_jobs, "_reservations_enabled", lambda: True)
    monkeypatch.setattr(reservation_jobs.reservations, "load_reservation_ledger", fake_load)
    monkeypatch.setattr(reservation_jobs.reservations, "update_reservation_status", fake_update)
    monkeypatch.setattr(reservation_jobs.availability, "recompute_clan_availability", fake_recompute)
    monkeypatch.setattr(reservation_jobs, "get_recruiters_thread_id", lambda: 4444)

    asyncio.run(reservation_jobs.reservations_autorelease_daily(bot=bot, today=today))

    assert updates == [(2, "expired", 6)]
    assert len(fake_thread.sent) == 1
    assert "expired" in fake_thread.sent[0]
    assert summary_thread.sent and "auto-release" in summary_thread.sent[0]
    assert recomputed == ["AAA"]
