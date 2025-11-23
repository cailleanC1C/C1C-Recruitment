import asyncio
import datetime as dt
from types import SimpleNamespace

from modules.placement import reservation_jobs
from shared.sheets import reservations


class FakeChannel:
    def __init__(
        self,
        channel_id: int,
        *,
        guild: object | None = None,
        name: str = "W0000-Test",
    ) -> None:
        self.id = channel_id
        self.guild = guild or SimpleNamespace(id=1234)
        self.name = name
        self.sent: list[str] = []
        self.archived = False

    async def send(self, *, content: str | None = None, **_: object) -> None:
        if content is not None:
            self.sent.append(content)

    async def edit(self, **kwargs) -> None:
        if "name" in kwargs:
            self.name = kwargs["name"]
        if "archived" in kwargs:
            self.archived = kwargs["archived"]


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
    username_snapshot: str = "Recruit One",
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
        username_snapshot=username_snapshot,
        raw=[
            str(thread_id),
            str(ticket_user_id or ""),
            "3000",
            clan_tag,
            reserved_until.isoformat() if reserved_until else "",
            "",
            status,
            "",
            username_snapshot,
        ],
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

    ledger = reservations.ReservationLedger(
        rows=[due_row, future_row],
        status_index=reservations.STATUS_COLUMN_INDEX,
    )

    async def fake_load():
        return ledger

    recomputed: list[tuple[str, object | None]] = []

    async def fake_recompute(clan_tag: str, *, guild=None):
        recomputed.append((clan_tag, guild))

    fake_thread = FakeChannel(5555, name="Res-W0455-ReminderUser-C1CE")
    recruiters_channel = FakeChannel(9999, guild=fake_thread.guild)
    bot = FakeBot({5555: fake_thread, 9999: recruiters_channel})

    monkeypatch.setattr(reservation_jobs, "_reservations_enabled", lambda: True)
    monkeypatch.setattr(reservation_jobs.reservations, "load_reservation_ledger", fake_load)
    monkeypatch.setattr(reservation_jobs.availability, "recompute_clan_availability", fake_recompute)
    monkeypatch.setattr(reservation_jobs, "get_recruiter_role_ids", lambda: {42})
    monkeypatch.setattr(reservation_jobs, "get_recruiters_channel_id", lambda: 9999)

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reservation_jobs.human_log, "human", fake_log)

    asyncio.run(reservation_jobs.reservations_reminder_daily(bot=bot, today=today))

    assert len(recruiters_channel.sent) == 1
    assert not fake_thread.sent
    content = recruiters_channel.sent[0]
    lines = content.splitlines()
    assert lines[0] == "<@&42>"
    assert lines[1].startswith("📌 **Reservation ending today**")
    assert "auto-release" in content or "release" in content
    assert "Ticket: https://discord.com/channels/1234/5555" in content

    assert recomputed == [("AAA", fake_thread.guild)]
    assert logs and "reservation_reminder" in logs[0] and "result=notified" in logs[0]


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
        status_index=reservations.STATUS_COLUMN_INDEX,
    )

    async def fake_load():
        return ledger

    updates: list[tuple[int, str, int | None]] = []

    async def fake_update(row_number: int, status: str, *, status_column: int | None = None):
        updates.append((row_number, status, status_column))

    recomputed: list[str] = []

    async def fake_recompute(clan_tag: str, *, guild=None):
        recomputed.append(clan_tag)

    log_channel = FakeChannel(4444)
    fake_thread = FakeChannel(7777, name="Res-W0777-User-C1CT")
    bot = FakeBot({7777: fake_thread, 4444: log_channel})

    monkeypatch.setattr(reservation_jobs, "_reservations_enabled", lambda: True)
    monkeypatch.setattr(reservation_jobs.reservations, "load_reservation_ledger", fake_load)
    monkeypatch.setattr(reservation_jobs.reservations, "update_reservation_status", fake_update)
    monkeypatch.setattr(reservation_jobs.availability, "recompute_clan_availability", fake_recompute)
    monkeypatch.setattr(reservation_jobs, "get_logging_channel_id", lambda: 4444)

    asyncio.run(reservation_jobs.reservations_autorelease_daily(bot=bot, today=today))

    assert updates == [(2, "expired", 6)]
    assert len(fake_thread.sent) == 1
    assert "expired" in fake_thread.sent[0]
    assert fake_thread.name == "W0777-User"
    assert log_channel.sent and "auto-release" in log_channel.sent[0]
    assert f"ticket=https://discord.com/channels/{fake_thread.guild.id}/7777" in log_channel.sent[0]
    assert recomputed == ["AAA"]
