"""Navigation and validation coverage for onboarding rules v2."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.onboarding import rules


@pytest.fixture(autouse=True)
def _enable_rules_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rules, "_toggle_enabled", lambda: True)


def _question(
    qid: str,
    *,
    nav_rules: str = "",
    visibility_rules: str = "",
    required: bool = True,
    order: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        qid=qid,
        type="single-select",
        nav_rules=nav_rules,
        visibility_rules=visibility_rules,
        required=required,
        label=qid,
        order=order,
        order_raw=order,
        rules="",
    )


def test_navigation_first_match_wins() -> None:
    questions = [
        _question(
            "w_siege",
            nav_rules='goto_if(value = "yes", target = "w_siege_detail")\n'
            'goto_if(value = "no", target = "w_cvc")',
        ),
        _question("w_siege_detail"),
        _question(
            "w_cvc",
            nav_rules='goto_if(int(value) >= 3, target="w_cvc_points")\n'
            'goto_if(int(value) < 3, target="w_origin")',
        ),
        _question("w_cvc_points"),
        _question("w_origin"),
    ]

    assert rules.next_index_by_rules(0, questions, {"w_siege": "yes"}) == 1
    assert rules.next_index_by_rules(0, questions, {"w_siege": "no"}) == 2
    assert rules.next_index_by_rules(2, questions, {"w_cvc": "2"}) == 4
    assert rules.next_index_by_rules(2, questions, {"w_cvc": "3"}) == 3


def test_navigation_cycle_guard_breaks_loop() -> None:
    questions = [
        _question(
            "w_cycle",
            nav_rules='goto_if(value = "loop", target="w_cycle")',
        ),
    ]

    assert rules.next_index_by_rules(0, questions, {"w_cycle": "loop"}) is None


def test_validate_rules_flags_unknown_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rules, "_toggle_enabled", lambda: True)
    questions = [
        _question(
            "w_target",
            visibility_rules='skip_if(w_missing = "x")',
        ),
        _question("w_source"),
    ]
    errors = rules.validate_rules(questions)
    assert any("unknown identifier" in error for error in errors)


def test_validate_rules_accepts_valid_dsl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rules, "_toggle_enabled", lambda: True)
    questions = [
        _question("w_gate"),
        _question(
            "w_branch",
            nav_rules='goto_if(value in [yes, maybe], target="w_gate")',
            visibility_rules='optional_if(w_gate = "open")',
        ),
    ]
    assert rules.validate_rules(questions) == []
