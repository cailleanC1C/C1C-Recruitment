"""Rules subsystem entrypoint with feature toggle support."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.common import feature_flags
from shared.sheets.onboarding_questions import Question

from . import legacy
from .evaluator import evaluate_navigation as _evaluate_navigation_v2
from .evaluator import evaluate_visibility as _evaluate_visibility_v2
from .parser import (
    BinaryExpression,
    Expression,
    FunctionCall,
    Identifier,
    ListLiteral,
    RuleParseError,
    UnaryExpression,
    parse_nav_rules,
    parse_visibility_rules,
)

__all__ = ["evaluate_visibility", "next_index_by_rules", "validate_rules"]


def _toggle_enabled() -> bool:
    try:
        return feature_flags.is_enabled("onboarding_rules_v2")
    except Exception:
        return False


def evaluate_visibility(
    questions: Sequence[Question],
    answers: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if _toggle_enabled():
        return _evaluate_visibility_v2(questions, answers)
    return legacy.evaluate_visibility(questions, answers)


def next_index_by_rules(
    current_idx: int, questions: Sequence[Question], answers: Mapping[str, Any]
) -> int | None:
    if _toggle_enabled():
        return _evaluate_navigation_v2(current_idx, questions, answers)
    return legacy.next_index_by_rules(current_idx, list(questions), dict(answers))


def validate_rules(questions: Sequence[Question]) -> list[str]:
    if _toggle_enabled():
        return _validate_v2(questions)
    return legacy.validate_rules(questions)


def _validate_v2(questions: Sequence[Question]) -> list[str]:
    errors: list[str] = []
    if not questions:
        return errors

    qid_lookup = {question.qid for question in questions}

    for question in questions:
        visibility_text = question.visibility_rules or ""
        if visibility_text:
            try:
                directives = parse_visibility_rules(visibility_text, qid=question.qid)
            except RuleParseError as exc:
                errors.append(f"{question.qid}: {exc}")
            else:
                for directive in directives:
                    errors.extend(
                        _validate_identifiers(
                            question.qid,
                            directive.expression,
                            qid_lookup,
                            allow_value=False,
                        )
                    )
        nav_text = question.nav_rules or ""
        if not nav_text:
            continue
        try:
            directives = parse_nav_rules(nav_text, qid=question.qid)
        except RuleParseError as exc:
            errors.append(f"{question.qid}: {exc}")
            continue
        for directive in directives:
            if directive.target not in qid_lookup:
                errors.append(
                    f"{question.qid}: navigation target '{directive.target}' is unknown"
                )
            errors.extend(
                _validate_identifiers(
                    question.qid,
                    directive.expression,
                    qid_lookup,
                    allow_value=True,
                )
            )
    return errors


def _validate_identifiers(
    owner_qid: str,
    expression: Expression,
    known_qids: set[str],
    *,
    allow_value: bool,
) -> list[str]:
    issues: list[str] = []
    for name in _iter_identifiers(expression):
        lowered = name.lower()
        if lowered == "value" and allow_value:
            continue
        if lowered in {"true", "false"}:  # allow boolean tokens
            continue
        if lowered == "value" and not allow_value:
            issues.append(f"{owner_qid}: 'value' is not valid in visibility rules")
            continue
        if name not in known_qids:
            issues.append(f"{owner_qid}: unknown identifier '{name}'")
    for func in _iter_functions(expression):
        if func.lower() != "int":
            issues.append(f"{owner_qid}: unsupported function '{func}'")
    return issues


def _iter_identifiers(expression: Expression) -> list[str]:
    found: list[str] = []
    stack: list[Expression] = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, Identifier):
            found.append(node.name)
            continue
        if isinstance(node, ListLiteral):
            stack.extend(node.items)
            continue
        if isinstance(node, UnaryExpression):
            stack.append(node.operand)
            continue
        if isinstance(node, BinaryExpression):
            stack.append(node.left)
            stack.append(node.right)
            continue
        if isinstance(node, FunctionCall):
            stack.extend(node.args)
    return found


def _iter_functions(expression: Expression) -> list[str]:
    found: list[str] = []
    stack: list[Expression] = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, FunctionCall):
            found.append(node.name)
            stack.extend(node.args)
            continue
        if isinstance(node, UnaryExpression):
            stack.append(node.operand)
            continue
        if isinstance(node, BinaryExpression):
            stack.append(node.left)
            stack.append(node.right)
            continue
        if isinstance(node, ListLiteral):
            stack.extend(node.items)
    return found
