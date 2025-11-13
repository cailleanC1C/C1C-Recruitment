import asyncio
from typing import List

import discord

from modules.placement import reservations as reserve_module


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
    def __init__(self, thread_id: int, parent_id: int) -> None:
        self.id = thread_id
        self.parent_id = parent_id
        self.type = discord.ChannelType.private_thread
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
    def __init__(self, messages: List[FakeMessage]) -> None:
        self._messages = list(messages)

    async def wait_for(self, event_name: str, *, timeout: float, check):
        while self._messages:
            message = self._messages.pop(0)
            if check(message):
                return message
        raise asyncio.TimeoutError


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
