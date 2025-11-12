from types import SimpleNamespace

from modules.onboarding.ui import summary_embed
from shared.sheets.onboarding_questions import Question


def _question(qid: str, label: str, qtype: str) -> Question:
    return Question(
        flow="welcome",
        order="1",
        qid=qid,
        label=label,
        type=qtype,
        required=True,
        maxlen=None,
        validate=None,
        help=None,
        options=tuple(),
        multi_max=None,
        rules=None,
    )


def test_summary_embed_formats_boolean_answers(monkeypatch):
    question = _question("siege_interest", "Interested in Siege?", "bool")
    monkeypatch.setattr(
        summary_embed.onboarding_questions,
        "get_questions",
        lambda flow: [question],
    )
    monkeypatch.setattr(
        summary_embed.onboarding_questions, "schema_hash", lambda flow: "hash123"
    )
    author = SimpleNamespace(display_name="Recruit", display_avatar=None)

    embed_true = summary_embed.build_summary_embed(
        "promo",
        {"siege_interest": True},
        author,
        schema_hash="hash123",
    )
    assert embed_true.fields[0].value == "Yes"

    embed_false = summary_embed.build_summary_embed(
        "promo",
        {"siege_interest": "no"},
        author,
        schema_hash="hash123",
    )
    assert embed_false.fields[0].value == "No"
