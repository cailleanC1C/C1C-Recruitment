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


def test_build_embed_from_rows_filters_and_groups():
    rows = _sample_rows()
    headers = dru._headers_map(rows[0])
    embed = dru._build_embed_from_rows(rows, headers)

    assert isinstance(embed, Embed)
    # Three logical blocks plus dividers and per-bracket detail sections
    assert len(embed.fields) == 7

    general_field = embed.fields[0]
    assert general_field.name == "General Overview"
    assert "Ops Summary" in general_field.value
    assert "Ops Idle" not in general_field.value

    divider_field = embed.fields[1]
    assert divider_field.name.strip() == ""
    assert divider_field.value in {"﹘﹘﹘", "▫▪▫▪▫▪▫"}

    per_bracket = embed.fields[2]
    assert per_bracket.name == "**Per Bracket**"
    assert "Elite End Game: open 2 | inactives 0 | reserved 1" in per_bracket.value
    assert "Mid Game: open 0 | inactives 0 | reserved 0" in per_bracket.value

    second_divider = embed.fields[3]
    assert second_divider.name.strip() == ""
    assert second_divider.value in {"﹘﹘﹘", "▫▪▫▪▫▪▫"}

    detail_header = embed.fields[4]
    assert detail_header.name == "**Bracket Details**"
    assert detail_header.value.strip() == ""

    elite_end_game = embed.fields[5]
    assert elite_end_game.name == "Elite End Game"
    assert elite_end_game.inline is False
    assert "Clan Alpha" in elite_end_game.value
    assert "Clan Beta" not in elite_end_game.value

    mid_game = embed.fields[6]
    assert mid_game.name == "Mid Game"
    assert mid_game.inline is False
    assert "Clan Delta" in mid_game.value


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
