import asyncio
import sys
import types

import discord
import pytest
from discord.ext import commands

# Seed legacy helpers expected by runtime imports
_coreops = types.ModuleType("c1c_coreops")
_coreops_helpers = types.ModuleType("c1c_coreops.helpers")
_coreops_helpers.audit_tiers = lambda *args, **kwargs: None
_coreops_helpers.rehydrate_tiers = lambda *args, **kwargs: None
_coreops.helpers = _coreops_helpers  # type: ignore[attr-defined]
sys.modules.setdefault("c1c_coreops", _coreops)
sys.modules.setdefault("c1c_coreops.helpers", _coreops_helpers)

from cogs.recruitment_member import RecruitmentMember
from modules.recruitment import cards, search_helpers
from modules.recruitment.views import member_panel, member_panel_legacy
from modules.recruitment.views.member_panel import (
    ACTIVE_PANELS,
    MemberPanelController,
    MemberSearchFilters,
)
from modules.recruitment.views.filters_member import MemberFiltersView


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
        if content is not None:
            self.content = content
        if embeds is not None:
            self.embeds = list(embeds)
        if attachments is not None:
            self.files = list(attachments)
        if view is not None:
            self.view = view
        self.edit_calls.append({"content": content, "embeds": self.embeds, "view": view})
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
        raise discord.NotFound(response=None, message="missing")


class FakeAuthor:
    def __init__(self, user_id=10):
        self.id = user_id
        self.mention = f"<@{user_id}>"


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

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


class FakeInteractionResponse:
    def __init__(self):
        self._done = False

    def is_done(self):
        return self._done

    async def defer(self, *args, **kwargs):
        self._done = True

    async def send_message(self, *args, **kwargs):
        self._done = True


class FakeFollowup:
    def __init__(self, channel):
        self._channel = channel
        self.sent: list[FakeMessage] = []

    async def send(self, *args, **kwargs):
        message = await self._channel.send(*args, **kwargs)
        self.sent.append(message)
        return message

    async def edit_message(self, *, message_id, **kwargs):
        message = await self._channel.fetch_message(message_id)
        await message.edit(**kwargs)
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
    hydra="NM",
    chimera="NM",
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
    row[search_helpers.COL_E_SPOTS] = str(spots)
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
    ACTIVE_PANELS.clear()
    member_panel_legacy.ACTIVE_RESULTS.clear()
    monkeypatch.setattr(
        "modules.recruitment.views.shared_member.emoji_pipeline.tag_badge_defaults",
        lambda: (0, 0),
        raising=False,
    )

    async def _fake_thumbnail(*args, **kwargs):
        return None, None

    monkeypatch.setattr(
        "modules.recruitment.views.shared_member.emoji_pipeline.build_tag_thumbnail",
        _fake_thumbnail,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.recruitment.views.shared_member.emoji_pipeline.padded_emoji_url",
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

        rows = [["header"] * 40]

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
        panel_message = ctx.channel.messages[0]
        assert panel_message.view is not None

        selects = [child for child in panel_message.view.children if isinstance(child, discord.ui.Select)]
        assert len(selects) == 4
        assert {select.row for select in selects} == {0, 1, 2, 3}
        placeholders = {select.placeholder for select in selects}
        assert {
            "CB Difficulty (optional)",
            "Hydra Difficulty (optional)",
            "Chimera Difficulty (optional)",
            "Playstyle (optional)",
        } == placeholders

        buttons = [child for child in panel_message.view.children if isinstance(child, discord.ui.Button)]
        row_four = [button for button in buttons if button.row == 4]
        assert len(row_four) == 5
        labels = {button.label for button in row_four}
        assert labels == {
            "CvC: —",
            "Siege: —",
            "Open Spots Only",
            "Reset",
            "Search Clans",
        }

        await bot.close()

    asyncio.run(_run())


def test_search_edits_same_results_message(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        cog = RecruitmentMember(bot)
        ctx = FakeContext(bot)

        datasets = [
            [["header"] * 40, make_row("Clan A", tag="C1A", spots=3)],
            [["header"] * 40, make_row("Clan B", tag="C1B", spots=0)],
        ]
        call_count = {"value": 0}

        async def fake_fetch(**_):
            index = min(call_count["value"], len(datasets) - 1)
            call_count["value"] += 1
            return datasets[index]

        monkeypatch.setattr(
            "modules.recruitment.views.member_panel_legacy.fetch_clans_async",
            fake_fetch,
        )

        await RecruitmentMember.clansearch.callback(cog, ctx)
        assert len(ctx.channel.messages) == 1
        panel_message = ctx.channel.messages[0]
        view = panel_message.view
        assert view is not None

        search_button = next(
            child for child in view.children if isinstance(child, discord.ui.Button) and child.label == "Search Clans"
        )

        interaction = FakeInteraction(panel_message, user=ctx.author)
        await search_button.callback(interaction)  # type: ignore[misc]

        assert len(ctx.channel.messages) == 2
        results_message = ctx.channel.messages[1]
        assert isinstance(results_message.view, member_panel_legacy.MemberSearchPagedView)
        assert results_message.embeds

        second_interaction = FakeInteraction(panel_message, user=ctx.author)
        await search_button.callback(second_interaction)  # type: ignore[misc]

        assert len(ctx.channel.messages) == 2
        refreshed_message = ctx.channel.messages[1]
        assert refreshed_message.id == results_message.id
        assert refreshed_message.edit_calls

        await bot.close()

    asyncio.run(_run())


def test_zero_state_results_attach_pager_with_disabled_nav(monkeypatch):
    async def _run():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        cog = RecruitmentMember(bot)
        ctx = FakeContext(bot)

        rows = [["header"] * 40]

        async def fake_fetch(**_):
            return rows

        monkeypatch.setattr(
            "modules.recruitment.views.member_panel_legacy.fetch_clans_async",
            fake_fetch,
        )

        await RecruitmentMember.clansearch.callback(cog, ctx)
        panel_message = ctx.channel.messages[0]
        view = panel_message.view
        search_button = next(
            child for child in view.children if isinstance(child, discord.ui.Button) and child.label == "Search Clans"
        )

        interaction = FakeInteraction(panel_message, user=ctx.author)
        await search_button.callback(interaction)  # type: ignore[misc]

        assert len(ctx.channel.messages) == 2
        results_message = ctx.channel.messages[1]
        results_view = results_message.view
        assert isinstance(results_view, member_panel_legacy.MemberSearchPagedView)

        expected_disabled = {"ms_prev", "ms_next", "ms_lite", "ms_entry", "ms_profile"}
        for child in results_view.children:
            if isinstance(child, discord.ui.Button) and child.custom_id in expected_disabled:
                assert child.disabled, f"{child.custom_id} should be disabled when there are no results"

        await bot.close()

    asyncio.run(_run())


def test_entry_criteria_shows_ae_notes_when_present():
    row = make_row("Clan Notes", tag="CNOT", spots=5)
    while len(row) <= 30:
        row.append("")
    row[30] = "Additional entry notes go here."

    embed = cards.make_embed_for_row_search(row, filters_text="", guild=None)
    note_field = next((field for field in embed.fields if field.name == "Notes"), None)

    assert note_field is not None
    assert note_field.value == "Additional entry notes go here."


def test_roster_select_hides_inactives_and_renames_any():
    assert MemberFiltersView._cycle_roster("open") == "full"
    assert MemberFiltersView._cycle_roster("full") is None
    assert MemberFiltersView._cycle_roster(None) == "open"
    assert MemberFiltersView._cycle_roster("inactives") == "open"

    label_none, _ = MemberFiltersView._roster_visual(None)
    assert label_none == "Open or Full (no filter)"

    label_any, _ = MemberFiltersView._roster_visual("any")
    assert label_any == "Open or Full (no filter)"


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

    assert [match.row for match in matches] == [tuple(positive)]

