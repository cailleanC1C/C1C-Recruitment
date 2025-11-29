import pytest

from modules.onboarding.ui import summary_embed
from shared.sheets.onboarding_questions import Question


QUESTION_TYPES = {
    "w_ign": "short",
    "w_power": "number",
    "w_level_detail": "short",
    "w_playstyle": "short",
    "w_clan": "short",
    "w_CB": "short",
    "w_hydra_diff": "short",
    "w_hydra_clash": "number",
    "w_chimera_diff": "short",
    "w_chimera_clash": "number",
    "w_siege": "single",
    "w_siege_detail": "short",
    "w_cvc": "single",
    "w_cvc_points": "number",
    "w_level": "long",
    "w_origin": "short",
}


def _question(qid: str) -> Question:
    return Question(
        flow="welcome",
        order="1",
        qid=qid,
        label=qid,
        type=QUESTION_TYPES.get(qid, "short"),
        required=True,
        maxlen=None,
        validate=None,
        help=None,
        options=tuple(),
        multi_max=None,
        rules=None,
    )


def _stub_questions(monkeypatch: pytest.MonkeyPatch, *qids: str) -> None:
    questions = [_question(qid) for qid in qids]
    monkeypatch.setattr(summary_embed.onboarding_questions, "get_questions", lambda flow: questions)
    monkeypatch.setattr(summary_embed.onboarding_questions, "schema_hash", lambda flow: "hash")


def test_format_short_number_variants() -> None:
    assert summary_embed._format_short_number(950) == "950"
    assert summary_embed._format_short_number(10_500) == "10.5 K"
    assert summary_embed._format_short_number(12_600_000) == "12.6 M"
    assert summary_embed._format_short_number("42,000") == "42 K"


def test_hide_rules_and_siege_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_questions(monkeypatch, "w_siege", "w_siege_detail", "w_level", "w_origin")
    answers = {
        "w_siege": "no",
        "w_siege_detail": "Stacked defenses",
        "w_level": "",
        "w_origin": "dunno",
    }

    embed = summary_embed.build_summary_embed("welcome", answers, author=None, schema_hash="hash")
    assert len(embed.fields) == 1
    war_field = embed.fields[0]
    assert war_field.name == "⚔️ War Modes"
    assert "Siege participation" in war_field.value
    assert "Siege setup" not in war_field.value

    assert summary_embed._is_effectively_empty("no")
    assert summary_embed._is_effectively_empty("NONE")
    assert summary_embed._is_effectively_empty("dUnNo")
    assert not summary_embed._is_effectively_empty("yes")


def test_cvc_mapping_and_inline_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_questions(
        monkeypatch,
        "w_ign",
        "w_power",
        "w_level_detail",
        "w_hydra_diff",
        "w_hydra_clash",
        "w_chimera_diff",
        "w_chimera_clash",
        "w_siege",
        "w_cvc",
        "w_cvc_points",
    )
    answers = {
        "w_ign": "TestRecruit",
        "w_power": "10500",
        "w_level_detail": "Gold",
        "w_hydra_diff": "Normal",
        "w_hydra_clash": 320_000,
        "w_chimera_diff": "Hard",
        "w_chimera_clash": "1250000",
        "w_siege": "yes",
        "w_cvc": "4",
        "w_cvc_points": "42000",
    }

    embed = summary_embed.build_summary_embed("welcome", answers, author=None, schema_hash="hash")
    progress_field = next(field for field in embed.fields if field.name == "🧩 Progress & Bossing")
    assert "**Hydra:** Normal • **Avg Hydra Clash:** 320 K" in progress_field.value
    assert "**Chimera:** Hard" in progress_field.value

    war_field = next(field for field in embed.fields if field.name == "⚔️ War Modes")
    assert "**CvC priority:** High-Medium • **Minimum CvC points:** 42 K" in war_field.value

    # Unknown CvC priority falls back to the raw value and still renders inline pairs cleanly.
    answers["w_cvc"] = "maybe"
    embed_unknown = summary_embed.build_summary_embed("welcome", answers, author=None, schema_hash="hash")
    war_field_unknown = next(field for field in embed_unknown.fields if field.name == "⚔️ War Modes")
    assert "**CvC priority:** maybe" in war_field_unknown.value


def test_inline_helpers_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(summary_embed.onboarding_questions, "get_questions", lambda flow: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(summary_embed.onboarding_questions, "schema_hash", lambda flow: "hash")

    embed = summary_embed.build_summary_embed("welcome", {}, author=None, schema_hash="hash")
    assert isinstance(embed, summary_embed.discord.Embed)
    assert embed.description == "Summary unavailable — see logs"
    assert embed.title.startswith("🔥 C1C • Recruitment Summary")
    assert summary_embed._is_fallback_summary(embed)
