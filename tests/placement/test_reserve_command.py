import asyncio
import datetime as dt
from typing import List

import discord

from modules.placement import reservations as reserve_module
from shared.sheets import reservations as reservations_sheet


class FakeMember:
    def __init__(self, user_id: int, display_name: str = "Recruit") -> None:
        self.id = user_id
        self.display_name = display_name
        self.name = display_name
        self.mention = f"<@{user_id}>"


class FakeGuild:
    def __init__(self, members: List[FakeMember]) -> None:
        self._members = {member.id: member for member in members}

    def get_member(self, member_id: int):
        return self._members.get(member_id)


class FakeThread:
    def __init__(
        self,
        thread_id: int,
        parent_id: int,
        *,
        name: str = "W0000-Test",
        owner_id: int | None = None,
        guild: object | None = None,
    ) -> None:
        self.id = thread_id
        self.parent_id = parent_id
        self.type = discord.ChannelType.private_thread
        self.name = name
        self.owner_id = owner_id
        self.guild = guild
        self.sent: list[FakeSentMessage] = []

    async def send(self, content: str | None = None, **kwargs):
        message = FakeSentMessage(content, kwargs)
        self.sent.append(message)
        return message


class FakeSentMessage:
    def __init__(self, content: str | None, kwargs: dict) -> None:
        self.content = content
        self.kwargs = dict(kwargs)

    async def edit(self, *, content: str | None = None, **kwargs):
        if content is not None:
            self.content = content
        self.kwargs.update(kwargs)
        return self


class FakeMessage:
    def __init__(self, content: str, author, channel, mentions=None) -> None:
        self.content = content
        self.author = author
        self.channel = channel
        self.mentions = list(mentions or [])


class FakeBot:
    def __init__(self, messages: List[FakeMessage], *, channels: dict[int, FakeThread] | None = None) -> None:
        self._messages = list(messages)
        self._channels = dict(channels or {})

    async def wait_for(self, event_name: str, *, timeout: float, check):
        while self._messages:
            message = self._messages.pop(0)
            if check(message):
                return message
        raise asyncio.TimeoutError

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)


class FakeContext:
    def __init__(self, bot: FakeBot, guild: FakeGuild, channel: FakeThread, author) -> None:
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.author = author
        self.replies: list[FakeSentMessage] = []

    async def reply(self, content: str, *, mention_author: bool = False):
        message = await self.channel.send(content=content)
        self.replies.append(message)
        return message

    async def send(self, content: str, **kwargs):
        return await self.channel.send(content=content, **kwargs)


def _enable_feature(monkeypatch, enabled: bool = True) -> None:
    monkeypatch.setattr(
        reserve_module.feature_flags,
        "is_enabled",
        lambda key: enabled,
        raising=False,
    )


def _setup_parents(monkeypatch, parent_id: int) -> None:
    monkeypatch.setattr(reserve_module, "get_welcome_channel_id", lambda: parent_id)
    monkeypatch.setattr(reserve_module, "get_promo_channel_id", lambda: parent_id)


def _setup_permissions(monkeypatch, recruiter: bool, admin: bool = False) -> None:
    monkeypatch.setattr(reserve_module, "is_recruiter", lambda ctx: recruiter)
    monkeypatch.setattr(reserve_module, "is_admin_member", lambda ctx: admin)


def _make_cog(bot: FakeBot) -> reserve_module.ReservationCog:
    return reserve_module.ReservationCog(bot)  # type: ignore[arg-type]


def _reservation_row(
    row_number: int,
    *,
    clan_tag: str,
    reserved_until: dt.date | None = None,
    status: str = "active",
    thread_id: int = 555,
    ticket_user_id: int | None = 222,
    recruiter_id: int = 111,
    username_snapshot: str = "Recruit",
) -> reservations_sheet.ReservationRow:
    return reservations_sheet.ReservationRow(
        row_number=row_number,
        thread_id=str(thread_id),
        ticket_user_id=ticket_user_id,
        recruiter_id=recruiter_id,
        clan_tag=clan_tag,
        reserved_until=reserved_until,
        created_at=None,
        status=status,
        notes="",
        username_snapshot=username_snapshot,
        raw=[
            str(thread_id),
            str(ticket_user_id or ""),
            str(recruiter_id),
            clan_tag,
            reserved_until.isoformat() if reserved_until else "",
            "",
            status,
            "",
            username_snapshot,
        ],
    )


def test_reserve_success(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=999)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(222, "Recruit One")
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=555, parent_id=999)

    mention_message = FakeMessage("reserve user", author=None, channel=thread, mentions=[recruit])
    date_message = FakeMessage("2025-12-01", author=None, channel=thread)
    confirm_message = FakeMessage("yes", author=None, channel=thread)

    author = FakeMember(111, "Recruiter")
    for message in (mention_message, date_message, confirm_message):
        message.author = author

    bot = FakeBot([mention_message, date_message, confirm_message])
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    clan_row = ["", "Clan", "#ABC", "", "3"] + [""] * 40
    monkeypatch.setattr(reserve_module.recruitment, "find_clan_row", lambda tag: (10, list(clan_row)))

    def fake_updated_row(tag):
        updated = list(clan_row)
        while len(updated) <= 33:
            updated.append("")
        updated[31] = "1"
        updated[33] = "2"
        return updated

    monkeypatch.setattr(reserve_module.recruitment, "get_clan_by_tag", fake_updated_row)

    async def fake_count(tag):
        return 1

    monkeypatch.setattr(
        reserve_module.reservations,
        "count_active_reservations_for_clan",
        fake_count,
    )

    appended: list[list[str]] = []

    async def fake_append(row_values):
        appended.append(list(row_values))

    monkeypatch.setattr(reserve_module.reservations, "append_reservation_row", fake_append)

    recomputed = {}

    async def fake_recompute(clan_tag, *, guild=None, resolver=None):
        recomputed["tag"] = clan_tag

    monkeypatch.setattr(reserve_module.availability, "recompute_clan_availability", fake_recompute)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "ABC"))

    assert appended, "reservation row should be appended"
    saved_row = appended[0]
    assert saved_row[0] == str(thread.id)
    assert saved_row[1] == str(recruit.id)
    assert saved_row[3] == "#ABC"
    assert saved_row[6] == reserve_module.ACTIVE_STATUS
    assert saved_row[7] == ""
    assert saved_row[8] == recruit.display_name
    assert recomputed["tag"] == "#ABC"
    assert thread.sent[-1].content.startswith("Reserved 1 spot in `#ABC`")


def test_reserve_requires_reason(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=777)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(333, "Applicant")
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=666, parent_id=777)

    author = FakeMember(444, "Recruiter")
    messages = [
        FakeMessage("who", author=author, channel=thread, mentions=[recruit]),
        FakeMessage("2025-11-30", author=author, channel=thread),
        FakeMessage("Because they confirmed a start date", author=author, channel=thread),
        FakeMessage("yes", author=author, channel=thread),
    ]

    bot = FakeBot(messages)
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    clan_row = ["", "Clan", "#DEF", "", "1"] + [""] * 40
    monkeypatch.setattr(reserve_module.recruitment, "find_clan_row", lambda tag: (11, list(clan_row)))
    monkeypatch.setattr(reserve_module.recruitment, "get_clan_by_tag", lambda tag: clan_row)
    async def fake_count(tag):
        return 1

    monkeypatch.setattr(
        reserve_module.reservations,
        "count_active_reservations_for_clan",
        fake_count,
    )

    appended: list[list[str]] = []

    async def fake_append(row_values):
        appended.append(list(row_values))

    monkeypatch.setattr(reserve_module.reservations, "append_reservation_row", fake_append)
    monkeypatch.setattr(
        reserve_module.availability,
        "recompute_clan_availability",
        lambda *args, **kwargs: asyncio.sleep(0),
    )

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "DEF"))

    assert appended[0][7] == "Because they confirmed a start date"


def test_reserve_feature_disabled(monkeypatch):
    _enable_feature(monkeypatch, enabled=False)
    _setup_parents(monkeypatch, parent_id=1001)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(555)
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=777, parent_id=1001)
    author = FakeMember(556)

    bot = FakeBot([])
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "XYZ"))

    assert ctx.replies, "should reply when feature disabled"
    assert "disabled" in ctx.replies[0].content


def test_reserve_permission_denied(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=42)
    _setup_permissions(monkeypatch, recruiter=False, admin=False)

    recruit = FakeMember(777)
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=888, parent_id=42)
    author = FakeMember(778)

    bot = FakeBot([])
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "JKL"))

    assert ctx.replies, "should reply when user lacks permissions"
    assert "Only Recruiters" in ctx.replies[0].content


def test_reserve_requires_ticket_thread(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=500)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(888)
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=999, parent_id=123)  # parent does not match configured id
    author = FakeMember(889)

    bot = FakeBot([])
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "MNO"))

    assert ctx.replies, "should reply when outside ticket thread"
    assert "ticket thread" in ctx.replies[0].content


def test_reservations_thread_no_matches(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=600)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(900, "Recruit Thread")
    guild = FakeGuild([recruit])
    thread = FakeThread(
        thread_id=1000,
        parent_id=600,
        name="W0455-Recruit Thread",
        owner_id=recruit.id,
    )
    author = FakeMember(901)

    bot = FakeBot([], channels={thread.id: thread})
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    async def fake_lookup(*_, **__):
        return []

    monkeypatch.setattr(
        reserve_module.reservations,
        "find_active_reservations_for_recruit",
        fake_lookup,
    )

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    cog = _make_cog(bot)
    asyncio.run(cog.reservations_command.callback(cog, ctx))

    assert thread.sent and "No active reservations" in thread.sent[0].content
    assert logs and "result=empty" in logs[0]


def test_reservations_thread_lists_matches(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=601)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(910, "Thread User")
    guild = FakeGuild([recruit])
    thread = FakeThread(
        thread_id=1100,
        parent_id=601,
        name="W0460-Thread User",
        owner_id=recruit.id,
    )
    author = FakeMember(911)

    rows = [
        _reservation_row(
            3,
            clan_tag="#DEF",
            reserved_until=dt.date(2025, 11, 20),
            thread_id=thread.id,
            ticket_user_id=recruit.id,
            recruiter_id=author.id,
            username_snapshot="Thread User",
        ),
        _reservation_row(
            2,
            clan_tag="#ABC",
            reserved_until=dt.date(2025, 11, 18),
            thread_id=thread.id,
            ticket_user_id=recruit.id,
            recruiter_id=author.id,
            username_snapshot="Thread User",
        ),
    ]

    async def fake_lookup(*_, **__):
        return list(rows)

    monkeypatch.setattr(
        reserve_module.reservations,
        "find_active_reservations_for_recruit",
        fake_lookup,
    )

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    bot = FakeBot([], channels={thread.id: thread})
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reservations_command.callback(cog, ctx))

    assert thread.sent, "expected reservation listing"
    content = thread.sent[0].content
    lines = content.splitlines()
    assert lines[1].startswith("• `ABC`")
    assert lines[2].startswith("• `DEF`")
    assert any("result=ok" in entry for entry in logs)


def test_reservations_clan_listing(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_permissions(monkeypatch, recruiter=True)
    _setup_parents(monkeypatch, parent_id=700)

    recruit = FakeMember(920, "User One")
    guild = FakeGuild([recruit])
    thread = FakeThread(thread_id=1200, parent_id=700, name="W0470-Other", owner_id=recruit.id)
    author = FakeMember(921)

    clan_row = ["", "Clan", "C1CE", ""] + [""] * 10

    monkeypatch.setattr(reserve_module.recruitment, "find_clan_row", lambda tag: (5, clan_row))

    rows = [
        _reservation_row(
            5,
            clan_tag="C1CE",
            reserved_until=dt.date(2025, 11, 21),
            thread_id=1300,
            ticket_user_id=recruit.id,
            username_snapshot="User One",
        ),
        _reservation_row(
            6,
            clan_tag="C1CE",
            reserved_until=dt.date(2025, 11, 22),
            thread_id=1400,
            ticket_user_id=None,
            username_snapshot="User Two",
        ),
    ]

    async def fake_clan(tag):
        assert tag == "C1CE"
        return list(rows)

    monkeypatch.setattr(
        reserve_module.reservations,
        "get_active_reservations_for_clan",
        fake_clan,
    )

    thread_lookup = {
        1300: FakeThread(1300, parent_id=700, name="W0471-User One-C1CE", owner_id=recruit.id),
        1400: FakeThread(1400, parent_id=700, name="W0472-User Two-C1CE", owner_id=None),
    }

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    bot = FakeBot([], channels=thread_lookup)
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reservations_command.callback(cog, ctx, "C1CE"))

    assert thread.sent, "expected clan reservation listing"
    content = thread.sent[0].content
    assert "ticket W0471" in content
    assert "ticket unknown" not in content.splitlines()[1]
    assert any("scope=clan" in entry and "result=ok" in entry for entry in logs)


def test_reserve_release_success(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=800)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(930, "Release User")
    guild = FakeGuild([recruit])
    thread = FakeThread(
        thread_id=1500,
        parent_id=800,
        name="Res-W0480-Release User-C1CE",
        owner_id=recruit.id,
    )
    author = FakeMember(931)

    row = _reservation_row(
        8,
        clan_tag="C1CE",
        reserved_until=dt.date(2025, 11, 23),
        thread_id=thread.id,
        ticket_user_id=recruit.id,
        recruiter_id=author.id,
        username_snapshot="Release User",
    )

    async def fake_lookup(*_, **__):
        return [row]

    monkeypatch.setattr(
        reserve_module.reservations,
        "find_active_reservations_for_recruit",
        fake_lookup,
    )

    updated: list[tuple[int, str]] = []

    async def fake_status(row_number: int, status: str):
        updated.append((row_number, status))

    monkeypatch.setattr(
        reserve_module.reservations,
        "update_reservation_status",
        fake_status,
    )

    manual_adjustments: list[tuple[str, int]] = []

    async def fake_adjust(tag: str, delta: int):
        manual_adjustments.append((tag, delta))

    monkeypatch.setattr(reserve_module.availability, "adjust_manual_open_spots", fake_adjust)

    recomputed: list[str] = []

    async def fake_recompute(tag: str, *, guild=None):
        recomputed.append(tag)

    monkeypatch.setattr(reserve_module.availability, "recompute_clan_availability", fake_recompute)

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    bot = FakeBot([], channels={thread.id: thread})
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "release"))

    assert updated == [(8, "released")]
    assert manual_adjustments == [("C1CE", 1)]
    assert recomputed == ["C1CE"]
    assert thread.sent and "Released the reserved seat" in thread.sent[-1].content
    assert any("reservation_release" in entry and "result=ok" in entry for entry in logs)


def test_reserve_extend_success(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=801)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(940, "Extend User")
    guild = FakeGuild([recruit])
    thread = FakeThread(
        thread_id=1600,
        parent_id=801,
        name="Res-W0485-Extend User-C1CE",
        owner_id=recruit.id,
    )
    author = FakeMember(941)

    row = _reservation_row(
        10,
        clan_tag="C1CE",
        reserved_until=dt.date(2025, 11, 25),
        thread_id=thread.id,
        ticket_user_id=recruit.id,
        recruiter_id=author.id,
        username_snapshot="Extend User",
    )

    async def fake_lookup(*_, **__):
        return [row]

    monkeypatch.setattr(
        reserve_module.reservations,
        "find_active_reservations_for_recruit",
        fake_lookup,
    )

    updates: list[tuple[int, dt.date]] = []

    async def fake_expiry(row_number: int, new_date: dt.date):
        updates.append((row_number, new_date))

    monkeypatch.setattr(
        reserve_module.reservations,
        "update_reservation_expiry",
        fake_expiry,
    )

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    bot = FakeBot([], channels={thread.id: thread})
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "extend", "2999-01-01"))

    assert updates == [(10, dt.date(2999, 1, 1))]
    assert thread.sent and "Extended the reservation" in thread.sent[-1].content
    assert any("reservation_extend" in entry and "result=ok" in entry for entry in logs)


def test_reserve_extend_invalid_date(monkeypatch):
    _enable_feature(monkeypatch, enabled=True)
    _setup_parents(monkeypatch, parent_id=802)
    _setup_permissions(monkeypatch, recruiter=True)

    recruit = FakeMember(950, "Extend Fail")
    guild = FakeGuild([recruit])
    thread = FakeThread(
        thread_id=1700,
        parent_id=802,
        name="Res-W0488-Extend Fail-C1CE",
        owner_id=recruit.id,
    )
    author = FakeMember(951)

    row = _reservation_row(
        11,
        clan_tag="C1CE",
        reserved_until=dt.date(2025, 11, 30),
        thread_id=thread.id,
        ticket_user_id=recruit.id,
        recruiter_id=author.id,
        username_snapshot="Extend Fail",
    )

    async def fake_lookup(*_, **__):
        return [row]

    monkeypatch.setattr(
        reserve_module.reservations,
        "find_active_reservations_for_recruit",
        fake_lookup,
    )

    logs: list[str] = []

    def fake_log(level: str, message: str, **_):
        logs.append(message)

    monkeypatch.setattr(reserve_module.human_log, "human", fake_log)

    bot = FakeBot([], channels={thread.id: thread})
    ctx = FakeContext(bot, guild=guild, channel=thread, author=author)

    cog = _make_cog(bot)
    asyncio.run(cog.reserve.callback(cog, ctx, "extend", "2020-01-01"))

    assert thread.sent, "expected invalid date message"
    assert "valid date" in thread.sent[-1].content
    assert any("invalid_date" in entry for entry in logs)
