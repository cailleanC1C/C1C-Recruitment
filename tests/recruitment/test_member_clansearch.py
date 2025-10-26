import asyncio
import sys
import types

import pytest
import discord

from discord.ext import commands

_coreops = types.ModuleType("c1c_coreops")
_coreops_helpers = types.ModuleType("c1c_coreops.helpers")
_coreops_helpers.audit_tiers = lambda *args, **kwargs: None
_coreops_helpers.rehydrate_tiers = lambda *args, **kwargs: None
_coreops.helpers = _coreops_helpers  # type: ignore[attr-defined]
sys.modules.setdefault("c1c_coreops", _coreops)
sys.modules.setdefault("c1c_coreops.helpers", _coreops_helpers)

from cogs.recruitment_member import RecruitmentMember
from modules.recruitment import search_helpers
from modules.recruitment.views import member_panel, member_panel_legacy
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


class FakeInteractionResponse:
    def __init__(self):
        self._done = False

    def is_done(self):
        return self._done

    async def defer(self):
        self._done = True

    async def send_message(self, *args, **kwargs):  # pragma: no cover - defensive
        self._done = True


class FakeFollowup:
    def __init__(self, channel):
        self._channel = channel
        self.sent: list[FakeMessage] = []

    async def send(self, *args, **kwargs):
        message = await self._channel.send(*args, **kwargs)
        self.sent.append(message)
        return message


class FakeInteraction:
    def __init__(self, message, *, user=None):
        self.message = message
        self.user = user or FakeAuthor()
        self.response = FakeInteractionResponse()
        self.followup = FakeFollowup(message.channel)
        self.channel = message.channel
        self.guild = None


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
    row = [""] * (search_helpers.IDX_AG_INACTIVES + 1)
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
    row[search_helpers.IDX_AG_INACTIVES] = inactives
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
        reply_text = (ctx.replies[0].content or "").lower()
        assert "take a clan tag" in reply_text
        assert "doesn" in reply_text
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
        monkeypatch.setattr(member_panel_legacy, "fetch_clans_async", fake_fetch)

        original_add_item = member_panel.discord.ui.view._ViewWeights.add_item

        def _relaxed_add_item(self, item):
            if item.row is not None and self.weights[item.row] + item.width > 5:
                item.row = None
            return original_add_item(self, item)

        monkeypatch.setattr(
            member_panel.discord.ui.view._ViewWeights,
            "add_item",
            _relaxed_add_item,
        )

        await RecruitmentMember.clansearch.callback(cog, ctx)

        assert len(ctx.channel.messages) == 1
        message = ctx.channel.messages[0]
        assert message.view is not None
        assert message.embeds
        await bot.close()

    asyncio.run(_run())


def test_zero_state_has_view_and_disabled_nav(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        controller = MemberPanelController(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await controller.update_results(ctx, filters=MemberSearchFilters())

        assert len(ctx.channel.messages) == 1
        message = ctx.channel.messages[0]
        assert message.embeds
        assert message.view is not None
        view = message.view
        assert hasattr(view, "has_results")
        assert not view.has_results

        expected_disabled = {"ms_prev", "ms_next", "ms_lite", "ms_entry", "ms_profile"}
        for child in view.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id in expected_disabled:
                assert child.disabled, f"{child.custom_id} should be disabled"

        await bot.close()

    asyncio.run(_run())


def test_zero_state_edit_reuses_message_with_embed(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        controller = MemberPanelController(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await controller.update_results(ctx, filters=MemberSearchFilters())
        assert len(ctx.channel.messages) == 1
        message = ctx.channel.messages[0]

        await controller.update_results(ctx, filters=MemberSearchFilters())

        assert len(ctx.channel.messages) == 1
        assert message.edit_calls
        for call in message.edit_calls:
            assert call["embeds"], "edit should include at least one embed"

        await bot.close()

    asyncio.run(_run())


def test_view_callbacks_on_empty_do_not_400(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        controller = MemberPanelController(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 32]

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(member_panel, "fetch_clans_async", fake_fetch)

        await controller.update_results(ctx, filters=MemberSearchFilters())
        message = ctx.channel.messages[0]
        view = message.view
        interaction = FakeInteraction(message)

        await view._edit(interaction)

        assert message.edit_calls
        assert message.edit_calls[-1]["embeds"], "view edit should include an embed"

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


def test_filter_rows_skips_blank_roster_entries():
    controller = MemberPanelController(object())
    blank_roster = make_row("Clan X", tag="C1X", spots=0)
    blank_roster[search_helpers.COL_E_SPOTS] = "   "

    matches = controller._filter_rows(
        [blank_roster], MemberSearchFilters(roster_mode=None)
    )

    assert matches == []


def test_filter_rows_requires_positive_inactives():
    controller = MemberPanelController(object())
    positive = make_row("Clan Active", tag="C1A", spots=0, inactives="3")
    zero = make_row("Clan Zero", tag="C1Z", spots=0, inactives="0")

    matches = controller._filter_rows(
        [positive, zero], MemberSearchFilters(roster_mode="inactives")
    )

    assert matches == [positive]

