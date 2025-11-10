from types import SimpleNamespace

import pytest

from modules.onboarding import rules


def _question(order: str, qid: str, *, rule: str = "") -> SimpleNamespace:
    return SimpleNamespace(order_raw=order, order=order, qid=qid, rules=rule)


def test_validate_rules_accepts_goto_clauses() -> None:
    questions = [
        _question("101", "g_class"),
        _question("201", "g_role"),
        _question("301", "g_followup", rule="if g_role in [tank, heal] goto 401 else goto 501"),
        _question("401", "tank_question"),
        _question("501", "other_question"),
    ]

    assert rules.validate_rules(questions) == []


def test_validate_rules_flags_unknown_targets() -> None:
    questions = [
        _question("101", "g_role"),
        _question("201", "g_followup", rule="if g_role = tank goto 999"),
    ]

    errors = rules.validate_rules(questions)
    assert "unknown order '999'" in errors[0]


@pytest.mark.parametrize(
    "answer,expected",
    [
        ({"label": "Tank"}, "401"),
        ({"value": "heal"}, "401"),
        ("DPS", "501"),
        ("Scout", None),
    ],
)
def test_next_index_by_rules_handles_goto(answer, expected) -> None:
    questions = [
        _question(
            "101",
            "g_role",
            rule="if g_role in [tank, heal] goto 401; if g_role = dps goto 501",
        ),
        _question("201", "unused"),
        _question("401", "tank_q"),
        _question("501", "dps_q"),
    ]

    answers = {"g_role": answer}
    jump = rules.next_index_by_rules(0, questions, answers)

    if expected is None:
        assert jump is None
    else:
        assert jump is not None
        assert questions[jump].order_raw == expected
