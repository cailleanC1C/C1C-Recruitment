import asyncio
import pytest
import discord

from discord.ext import commands

from cogs.recruitment_member import RecruitmentMember
from modules.recruitment import search_helpers
from modules.recruitment.views import member_panel
from modules.recruitment.views.member_panel import MemberPanelController, MemberSearchFilters


class FakeMessage:
    _next_id = 100

    def __init__(self, channel, *, content=None, embeds=None, files=None, view=None):
        self.id = FakeMessage._next_id
        FakeMessage._next_id += 1
        self.channel = channel
        self.content = content
        self.embeds = list(embeds or [])
        self.files = list(files or [])
        self.view = view
        self.edit_calls: list[dict] = []

    async def edit(self, *, content=None, embeds=None, attachments=None, view=None):
        self.content = content
        if embeds is not None:
            self.embeds = list(embeds)
        if attachments is not None:
            self.files = list(attachments)
        if view is not None:
            self.view = view
        self.edit_calls.append({"content": content, "embeds": self.embeds})
        return self


class FakeChannel:
    def __init__(self, channel_id=1):
        self.id = channel_id
        self.messages: list[FakeMessage] = []

    async def send(self, *args, **kwargs):
        content = kwargs.pop("content", None)
        embeds = kwargs.pop("embeds", None)
        files = kwargs.pop("files", None)
        view = kwargs.pop("view", None)
        if args:
            content = args[0] if content is None else content
        message = FakeMessage(
            self,
            content=content,
            embeds=embeds,
            files=files,
            view=view,
        )
        self.messages.append(message)
        return message

    async def fetch_message(self, message_id):
        for message in self.messages:
            if message.id == message_id:
                return message
        raise member_panel.discord.NotFound(response=None, message="missing")


class FakeAuthor:
    def __init__(self, user_id=10):
        self.id = user_id


class FakeGuild:
    def __init__(self, guild_id=50):
        self.id = guild_id
        self.emojis = []


class FakeContext:
    def __init__(self, bot, *, channel=None, author=None, guild=None):
        self.bot = bot
        self.channel = channel or FakeChannel()
        self.author = author or FakeAuthor()
        self.guild = guild or FakeGuild()
        self.replies: list[FakeMessage] = []

    async def reply(self, *args, **kwargs):
        message = await self.channel.send(*args, **kwargs)
        self.replies.append(message)
        return message


def make_row(
    name: str,
    *,
    tag: str,
    spots: int,
    cb="UNM",
    hydra="Nightmare",
    chimera="Nightmare",
    cvc="1",
    siege="1",
    playstyle="Competitive",
    inactives="0",
):
    row = [""] * 32
    row[0] = "1"
    row[1] = name
    row[2] = tag
    row[3] = "10"
    row[4] = str(spots)
    row[search_helpers.COL_P_CB] = cb
    row[search_helpers.COL_Q_HYDRA] = hydra
    row[search_helpers.COL_R_CHIMERA] = chimera
    row[search_helpers.COL_S_CVC] = cvc
    row[search_helpers.COL_T_SIEGE] = siege
    row[search_helpers.COL_U_STYLE] = playstyle
    row[search_helpers.IDX_AF_INACTIVES] = inactives
    return row


@pytest.fixture(autouse=True)
def reset_panels(monkeypatch):
    member_panel.ACTIVE_PANELS.clear()
    monkeypatch.setattr(
        "modules.recruitment.emoji_pipeline.tag_badge_defaults", lambda: (0, 0),
        raising=False,
    )
    async def _fake_thumbnail(*args, **kwargs):
        return None, None

    monkeypatch.setattr(
        "modules.recruitment.emoji_pipeline.build_tag_thumbnail",
        _fake_thumbnail,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.recruitment.emoji_pipeline.padded_emoji_url",
        lambda *args, **kwargs: None,
        raising=False,
    )


def test_rejects_extra_args(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        cog = RecruitmentMember(bot)
        ctx = FakeContext(bot)

        await RecruitmentMember.clansearch.callback(cog, ctx, extra="something")

        assert ctx.replies
        assert "no arguments" in ctx.replies[0].content.lower()
        await bot.close()

    asyncio.run(_run())


def test_first_invocation_creates_message(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        cog = RecruitmentMember(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]
        rows.append(make_row("Clan A", tag="C1A", spots=2))
        rows.append(make_row("Clan B", tag="C1B", spots=1))

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await RecruitmentMember.clansearch.callback(cog, ctx)

        assert len(ctx.channel.messages) == 1
        message = ctx.channel.messages[0]
        assert message.view is not None
        assert message.embeds
        await bot.close()

    asyncio.run(_run())


def test_filter_change_edits_message(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        controller = MemberPanelController(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]
        rows.append(make_row("Clan A", tag="C1A", spots=2, cb="UNM"))
        rows.append(make_row("Clan B", tag="C1B", spots=1, cb="NM"))

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await controller.update_results(ctx, filters=MemberSearchFilters(cb="UNM"))
        assert len(ctx.channel.messages) == 1
        message = ctx.channel.messages[0]

        await controller.update_results(ctx, filters=MemberSearchFilters(cb="NM"))
        assert len(ctx.channel.messages) == 1
        assert message.edit_calls  # message was edited instead of sending a new one
        await bot.close()

    asyncio.run(_run())


def test_soft_cap_footer(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        controller = MemberPanelController(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]
        for idx in range(7):
            rows.append(make_row(f"Clan {idx}", tag=f"C1{idx}", spots=idx + 1))

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await controller.update_results(ctx, filters=MemberSearchFilters())
        message = ctx.channel.messages[0]
        assert message.embeds
        footer = message.embeds[-1].footer.text or ""
        assert "first 5 of 7" in footer
        await bot.close()

    asyncio.run(_run())

