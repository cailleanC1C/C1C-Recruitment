from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GSPREAD_CREDENTIALS", "{}")
os.environ.setdefault("RECRUITMENT_SHEET_ID", "sheet-id")

from modules.recruitment.summary_embed import build_welcome_summary_embed
from shared.formatters.summary import abbr_number, cvc_priority, inline_merge, is_hide_value


def _snapshot_path(name: str) -> Path:
    return Path(__file__).with_name("snapshots") / f"{name}.snap"


def test_abbr_number_variants() -> None:
    assert abbr_number(999) == "999"
    assert abbr_number("1200") == "1.2 K"
    assert abbr_number(12_600_000) == "12.6 M"


def test_cvc_priority_mapping() -> None:
    assert cvc_priority(1) == "Low"
    assert cvc_priority("5") == "High"
    assert cvc_priority("unknown") == "unknown"


def test_is_hide_value_normalises_tokens() -> None:
    assert is_hide_value("No") is True
    assert is_hide_value("dUnNo") is True
    assert is_hide_value("Maybe") is False


def test_inline_merge_compacts_pairs() -> None:
    merged = inline_merge("Power", "12.6 M", "Bracket", "Beginner")
    assert merged == "**Power:** 12.6 M • **Bracket:** Beginner"


def test_build_welcome_summary_embed_snapshot() -> None:
    answers = {
        "w_ign": "C1C Caillean",
        "w_power": "12600000",
        "w_level_detail": {"label": "Beginner", "value": "beginner"},
        "w_playstyle": "Competitive",
        "w_clan": "Active, social clan with Hydra focus",
        "w_CB": {"label": "Normal", "value": "normal"},
        "w_hydra_diff": {"label": "Normal", "value": "normal"},
        "w_hydra_clash": 320_000,
        "w_chimera_diff": {"label": "Easy", "value": "easy"},
        "w_chimera_clash": 240_000,
        "w_siege": "No",
        "w_siege_detail": "Bench and clean-up squads",
        "w_cvc": 4,
        "w_cvc_points": 60_000,
        "w_level": "Late-game damage dealer refining Hydra teams.",
        "w_origin": "A friend in global chat",
    }
    visibility = {gid: {"state": "show"} for gid in answers}

    avatar = SimpleNamespace(url="https://cdn.example.com/avatar.png")
    author = SimpleNamespace(display_name="Caillean", display_avatar=avatar, name="Caillean")

    embed = build_welcome_summary_embed(answers, visibility, author=author)
    snapshot = json.dumps(embed.to_dict(), indent=2, sort_keys=True)

    expected_path = _snapshot_path("test_summary_embed")
    expected = expected_path.read_text().strip()
    assert snapshot.strip() == expected
