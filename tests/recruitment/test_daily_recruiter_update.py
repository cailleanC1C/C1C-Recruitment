import asyncio
from discord import Embed
from unittest.mock import AsyncMock, MagicMock

from modules.recruitment.reporting import daily_recruiter_update as dru
from cogs.recruitment_reporting import RecruitmentReporting


def _sample_rows():
    return [
        ["Key", "Grouping", "Open Spots", "Inactives", "Reserved Spots"],
        ["General Overview", "", "", "", ""],
        ["Ops Summary", "", "3", "1", "0"],
        ["Ops Idle", "", "0", "0", "0"],
        ["Per Bracket", "", "", "", ""],
        ["Elite End Game", "", "2", "0", "1"],
        ["Mid Game", "", "0", "0", "0"],
        ["Bracket Details", "", "", "", ""],
        ["", "Elite End Game", "", "", ""],
        ["Clan Alpha", "", "5", "0", "1"],
        ["Clan Beta", "", "0", "0", "0"],
        ["", "", "", "", ""],
        ["", "Mid Game", "", "", ""],
        ["Clan Delta", "", "2", "2", "0"],
    ]


def test_build_embeds_from_rows_filters_and_groups():
    rows = _sample_rows()
    headers = dru._headers_map(rows[0])
    summary_embed, details_embed = dru._build_embeds_from_rows(rows, headers)

    assert isinstance(summary_embed, Embed)
    assert isinstance(details_embed, Embed)

    assert summary_embed.title == "Summary Open Spots"
    assert details_embed.title == "Bracket Details"

    assert len(summary_embed.fields) == 3

    general_field = summary_embed.fields[0]
    assert general_field.name == "General Overview"
    assert "🔹 **Ops Summary:** open 3" in general_field.value
    assert "Ops Idle" not in general_field.value

    divider_field = summary_embed.fields[1]
    assert divider_field.name.strip() == ""
    assert divider_field.value in {"﹘﹘﹘", "▫▪▫▪▫▪▫"}

    per_bracket = summary_embed.fields[2]
    assert per_bracket.name == "Per Bracket"
    assert "🔹 **Elite End Game:** open 2 | inactives 0 | reserved 1" in per_bracket.value
    assert "🔹 **Mid Game:** open 0 | inactives 0 | reserved 0" in per_bracket.value

    assert len(details_embed.fields) == 2

    elite_end_game = details_embed.fields[0]
    assert elite_end_game.name == "Elite End Game"
    assert elite_end_game.inline is False
    assert "🔹 **Clan Alpha:** open 5 | inactives 0 | reserved 1" in elite_end_game.value
    assert "Clan Beta" not in elite_end_game.value

    mid_game = details_embed.fields[1]
    assert mid_game.name == "Mid Game"
    assert mid_game.inline is False
    assert "🔹 **Clan Delta:** open 2 | inactives 2 | reserved 0" in mid_game.value


def test_open_spots_pager_switches_pages():
    rows = _sample_rows()
    headers = dru._headers_map(rows[0])
    sections = dru._extract_report_sections(rows, headers)

    async def runner():
        pager = dru.OpenSpotsPager(sections)

        interaction_details = MagicMock()
        interaction_details.response = AsyncMock()
        interaction_details.response.edit_message = AsyncMock()
        interaction_details.response.defer = AsyncMock()

        await pager.set_details(interaction_details)

        interaction_summary = MagicMock()
        interaction_summary.response = AsyncMock()
        interaction_summary.response.edit_message = AsyncMock()
        interaction_summary.response.defer = AsyncMock()

        await pager.set_summary(interaction_summary)

        return pager, interaction_details, interaction_summary

    pager, interaction_details, interaction_summary = asyncio.run(runner())

    assert pager.current_page == "summary"
    assert pager.summary_button.disabled is True
    assert pager.details_button.disabled is False

    args, kwargs = interaction_details.response.edit_message.await_args
    assert kwargs["embeds"][0].title == "Bracket Details"

    args, kwargs = interaction_summary.response.edit_message.await_args
    assert kwargs["embeds"][0].title == "Summary Open Spots"


def test_post_daily_recruiter_update_sends_pager(monkeypatch):
    rows = _sample_rows()
    headers = dru._headers_map(rows[0])

    async def fake_fetch():
        return rows, headers

    class DummyChannel:
        def __init__(self):
            self.sent = []
            self.guild = None

        async def send(self, **kwargs):
            self.sent.append(kwargs)

    channel = DummyChannel()

    bot = MagicMock()
    bot.get_channel.return_value = channel
    bot.fetch_channel = AsyncMock()
    bot.wait_until_ready = AsyncMock()

    monkeypatch.setattr(dru, "_fetch_report_rows", fake_fetch)
    monkeypatch.setattr(dru, "get_report_destination_id", lambda: 123)
    monkeypatch.setattr(dru, "_role_mentions", lambda: ())
    monkeypatch.setattr(dru.discord, "TextChannel", DummyChannel)

    ok, error = asyncio.run(dru.post_daily_recruiter_update(bot))

    assert ok is True
    assert error == "-"
    assert channel.sent
    sent_kwargs = channel.sent[0]
    assert len(sent_kwargs["embeds"]) == 1
    assert isinstance(sent_kwargs["view"], dru.OpenSpotsPager)


def test_parse_utc_time_returns_aware_time():
    parsed = dru._parse_utc_time("09:30")
    assert parsed.hour == 9
    assert parsed.minute == 30
    assert parsed.tzinfo is dru.UTC


def test_report_command_feature_disabled(monkeypatch):
    monkeypatch.setattr("cogs.recruitment_reporting.feature_enabled", lambda: False)

    log_calls = []

    async def fake_log_manual_result(**kwargs):
        log_calls.append(kwargs)

    monkeypatch.setattr(
        "cogs.recruitment_reporting.log_manual_result", fake_log_manual_result
    )

    bot = MagicMock()
    cog = RecruitmentReporting(bot)

    ctx = MagicMock()
    ctx.reply = AsyncMock()
    ctx.author.id = 42

    async def runner() -> None:
        await cog.report_group.callback(cog, ctx, "recruiters")

    asyncio.run(runner())

    ctx.reply.assert_awaited_once_with("Daily Recruiter Update is disabled.", mention_author=False)
    assert log_calls
    assert log_calls[0]["result"] == "blocked"
