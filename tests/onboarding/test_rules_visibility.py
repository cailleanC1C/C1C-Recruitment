"""Integration tests for the onboarding rules v2 evaluator."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from modules.onboarding import rules, submit

_VISIBILITY_DIRECTIVES = (
    'skip_if(w_level_detail = "Beginner")\n'
    'optional_if(w_level_detail = "Early Game")'
)

_TARGET_QIDS = [
    "w_hydra_diff",
    "w_hydra_clash",
    "w_chimera_diff",
    "w_chimera_clash",
    "w_siege",
    "w_siege_detail",
    "w_cvc",
    "w_cvc_points",
]


@pytest.fixture(autouse=True)
def _enable_rules_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rules, "_toggle_enabled", lambda: True)


def _question(
    qid: str,
    *,
    required: bool = True,
    visibility_rules: str = "",
    nav_rules: str = "",
    qtype: str = "short",
    label: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        qid=qid,
        type=qtype,
        required=required,
        visibility_rules=visibility_rules,
        nav_rules=nav_rules,
        label=label or qid,
        rules="",
    )


@pytest.fixture()
def _visibility_questions() -> list[SimpleNamespace]:
    questions = [_question("w_level_detail", required=True, qtype="single-select", label="Stage")]
    for qid in _TARGET_QIDS:
        questions.append(
            _question(qid, visibility_rules=_VISIBILITY_DIRECTIVES, label=qid.replace("_", " "))
        )
    return questions


def _answers(level_detail: str) -> dict[str, Any]:
    return {"w_level_detail": level_detail}


@pytest.mark.parametrize(
    "level_detail,expected_state,expected_required",
    [
        ("Beginner", "skip", False),
        ("Early Game", "optional", False),
        ("Mid Game", "show", True),
    ],
)
def test_visibility_precedence(level_detail, expected_state, expected_required, _visibility_questions):
    visibility = rules.evaluate_visibility(_visibility_questions, _answers(level_detail))
    for qid in _TARGET_QIDS:
        assert visibility[qid]["state"] == expected_state
        assert bool(visibility[qid]["required"]) is expected_required


def test_server_side_requiredness_matches_visibility(_visibility_questions) -> None:
    visibility = rules.evaluate_visibility(_visibility_questions, _answers("Mid Game"))
    missing = submit.missing_required_questions(
        _visibility_questions,
        visibility,
        answers={},
    )
    missing_ids = {question.qid for question in missing}
    assert set(_TARGET_QIDS).issubset(missing_ids)

    beginner_visibility = rules.evaluate_visibility(_visibility_questions, _answers("Beginner"))
    missing_beginner = submit.missing_required_questions(
        _visibility_questions,
        beginner_visibility,
        answers={},
    )
    assert all(question.qid not in _TARGET_QIDS for question in missing_beginner)


def test_boolean_literals_in_visibility_rules() -> None:
    questions = [
        _question("w_intro", required=True, qtype="single-select"),
        _question("w_flag", visibility_rules="skip_if(true)"),
    ]

    visibility = rules.evaluate_visibility(questions, answers={})

    assert visibility["w_flag"]["state"] == "skip"
    assert visibility["w_flag"]["required"] is False
