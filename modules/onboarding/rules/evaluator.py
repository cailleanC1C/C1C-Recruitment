"""Evaluator for onboarding rules v2."""

from __future__ import annotations

from collections.abc import Iterable as IterableABC
from dataclasses import dataclass
import logging
import math
import re
from typing import Any, Mapping, Sequence

from modules.onboarding import diag
from shared.sheets.onboarding_questions import Question

from .parser import (
    BinaryExpression,
    Expression,
    FunctionCall,
    Identifier,
    ListLiteral,
    Literal,
    NavDirective,
    RuleParseError,
    UnaryExpression,
    VisibilityDirective,
    parse_nav_rules,
    parse_visibility_rules,
)

log = logging.getLogger("c1c.onboarding.rules")

MAX_VISIBILITY_PASSES = 5
MAX_NAV_HOPS = 10


@dataclass
class QuestionState:
    visible: bool
    required: bool

    def humanized(self) -> str:
        if not self.visible:
            return "skip"
        return "required" if self.required else "optional"


class _EvalContext:
    def __init__(self, *, answers: Mapping[str, Any], current_qid: str | None = None) -> None:
        self._answers = answers
        self._current_qid = current_qid

    def tokens(self, name: str) -> list[str]:
        source = None
        if name.lower() == "value":
            if self._current_qid is None:
                return []
            source = self._answers.get(self._current_qid)
        else:
            source = self._answers.get(name)
            if source is None:
                source = self._answers.get(name.lower())
        return _extract_tokens(source)

    def first_token(self, name: str) -> str | None:
        tokens = self.tokens(name)
        return tokens[0] if tokens else None


def _extract_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        tokens: list[str] = []
        for key in ("value", "label"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                tokens.append(raw.strip())
        nested = value.get("values")
        if isinstance(nested, IterableABC) and not isinstance(nested, (str, bytes, bytearray)):
            for item in nested:
                tokens.extend(_extract_tokens(item))
        return tokens
    if isinstance(value, IterableABC) and not isinstance(value, (str, bytes, bytearray)):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_extract_tokens(item))
        return tokens
    return [str(value).strip()]


_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _looks_numeric(value: str | None) -> bool:
    if value is None:
        return False
    return bool(_NUMERIC_RE.fullmatch(value.strip()))


def _to_float(value: str) -> float:
    return float(value.strip())


def _evaluate(expr: Expression, context: _EvalContext) -> Any:
    if isinstance(expr, Literal):
        return expr.value
    if isinstance(expr, Identifier):
        return context.tokens(expr.name)
    if isinstance(expr, ListLiteral):
        return [_evaluate(item, context) for item in expr.items]
    if isinstance(expr, UnaryExpression):
        operand = _evaluate(expr.operand, context)
        if expr.op == "not":
            return not _truthy(operand)
        raise ValueError(f"unsupported unary operator: {expr.op}")
    if isinstance(expr, BinaryExpression):
        left = _evaluate(expr.left, context)
        right = _evaluate(expr.right, context)
        return _evaluate_binary(expr.op, left, right)
    if isinstance(expr, FunctionCall):
        if expr.name.lower() == "int":
            if len(expr.args) != 1:
                raise ValueError("int() expects a single argument")
            value = _evaluate(expr.args[0], context)
            token = _first_scalar(value)
            if token is None:
                raise ValueError("int() missing value")
            return int(float(token))
        raise ValueError(f"unsupported function: {expr.name}")
    raise ValueError("unsupported expression node")


def _first_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, IterableABC) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            candidate = _first_scalar(item)
            if candidate is not None:
                return candidate
        return None
    return str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_truthy(item) for item in value)
    if isinstance(value, dict):
        return any(_truthy(item) for item in value.values())
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _evaluate_binary(op: str, left: Any, right: Any) -> bool:
    if op in {"=", "!=", "<", "<=", ">", ">="}:
        return _compare_values(op, left, right)
    if op == "in":
        return _evaluate_membership(left, right)
    if op == "and":
        return _truthy(left) and _truthy(right)
    if op == "or":
        return _truthy(left) or _truthy(right)
    raise ValueError(f"unsupported operator: {op}")


def _iter_scalars(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_iter_scalars(item))
        return result
    if isinstance(value, tuple):
        return _iter_scalars(list(value))
    if isinstance(value, set):
        return _iter_scalars(list(value))
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if value is None:
        return []
    return [str(value).strip()]


def _compare_values(op: str, left: Any, right: Any) -> bool:
    left_values = _iter_scalars(left)
    right_values = _iter_scalars(right)
    if op in {"=", "!="}:
        lhs = left_values or [_first_scalar(left)]
        rhs = right_values or [_first_scalar(right)]
        lhs_clean = [value for value in lhs if value is not None]
        rhs_clean = [value for value in rhs if value is not None]
        if not lhs_clean:
            return op == "!=" if rhs_clean else op == "="
        if not rhs_clean:
            return op == "!="
        if op == "=":
            for candidate in lhs_clean:
                for target in rhs_clean:
                    if _equals(candidate, target):
                        return True
            return False
        for candidate in lhs_clean:
            for target in rhs_clean:
                if _equals(candidate, target):
                    return False
        return True
    rhs_scalar = right_values[0] if right_values else _first_scalar(right)
    if rhs_scalar is None or not _looks_numeric(rhs_scalar):
        return False
    rhs_value = _to_float(rhs_scalar)
    lhs_candidates = left_values or [_first_scalar(left)]
    for candidate in lhs_candidates:
        if candidate is None or not _looks_numeric(candidate):
            continue
        lhs_value = _to_float(candidate)
        if op == "<" and lhs_value < rhs_value:
            return True
        if op == "<=" and lhs_value <= rhs_value:
            return True
        if op == ">" and lhs_value > rhs_value:
            return True
        if op == ">=" and lhs_value >= rhs_value:
            return True
    return False


def _equals(lhs: str | None, rhs: str | None) -> bool:
    if lhs is None or rhs is None:
        return False
    if _looks_numeric(lhs) and _looks_numeric(rhs):
        try:
            return math.isclose(_to_float(lhs), _to_float(rhs))
        except ValueError:
            return False
    return lhs == rhs


def _evaluate_membership(left: Any, right: Any) -> bool:
    left_values = _iter_scalars(left)
    right_values = _iter_scalars(right)
    if not right_values:
        return False
    for candidate in left_values or [_first_scalar(left)]:
        if candidate is None:
            continue
        if candidate in right_values:
            return True
    return False


def evaluate_visibility(
    questions: Sequence[Question],
    answers: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    states: dict[str, QuestionState] = {
        question.qid: QuestionState(visible=True, required=bool(question.required))
        for question in questions
    }
    directives_by_qid: dict[str, list[VisibilityDirective]] = {}
    for question in questions:
        text = question.visibility_rules or ""
        try:
            directives_by_qid[question.qid] = parse_visibility_rules(text, qid=question.qid)
        except RuleParseError as exc:
            _log_rule_error(question.qid, text, "parse", str(exc))
            directives_by_qid[question.qid] = []
    context = _EvalContext(answers=answers)
    for _pass in range(MAX_VISIBILITY_PASSES):
        changed = False
        for question in questions:
            current = states[question.qid]
            directives = directives_by_qid.get(question.qid, [])
            for directive in directives:
                try:
                    context_value = _evaluate(directive.expression, context)
                except Exception as exc:
                    _log_rule_error(question.qid, directive.raw, "eval", str(exc))
                    continue
                if not _truthy(context_value):
                    continue
                new_state = _apply_visibility(directive.kind, current)
                if new_state != current:
                    states[question.qid] = new_state
                    changed = True
                    _log_flip(question.qid, current, new_state, directive.raw)
                    current = new_state
        if not changed:
            break
    return {
        qid: {
            "state": "skip"
            if not state.visible
            else ("optional" if not state.required else "show"),
            "required": bool(state.required),
        }
        for qid, state in states.items()
    }


def _apply_visibility(kind: str, state: QuestionState) -> QuestionState:
    if kind == "skip":
        return QuestionState(visible=False, required=False)
    if kind == "show":
        if not state.visible:
            return state
        return QuestionState(visible=True, required=state.required)
    if kind == "optional":
        if not state.visible:
            return state
        return QuestionState(visible=True, required=False)
    if kind == "require":
        if not state.visible:
            return state
        return QuestionState(visible=True, required=True)
    return state


def evaluate_navigation(
    current_index: int,
    questions: Sequence[Question],
    answers: Mapping[str, Any],
) -> int | None:
    if current_index < 0 or current_index >= len(questions):
        return None
    qid_to_index = {question.qid: idx for idx, question in enumerate(questions)}
    visited: set[str] = set()
    hops = 0
    next_index: int | None = None
    idx = current_index
    while hops < MAX_NAV_HOPS:
        question = questions[idx]
        directives: list[NavDirective]
        try:
            directives = parse_nav_rules(question.nav_rules or "", qid=question.qid)
        except RuleParseError as exc:
            _log_rule_error(question.qid, question.nav_rules or "", "parse", str(exc))
            break
        if not directives:
            break
        context = _EvalContext(answers=answers, current_qid=question.qid)
        triggered = False
        for directive in directives:
            try:
                result = _evaluate(directive.expression, context)
            except Exception as exc:
                _log_rule_error(question.qid, directive.raw, "eval", str(exc))
                continue
            if not _truthy(result):
                continue
            target_idx = qid_to_index.get(directive.target)
            if target_idx is None:
                _log_rule_error(question.qid, directive.raw, "resolve", f"unknown target {directive.target}")
                continue
            _log_nav(question.qid, questions[target_idx].qid, directive.raw)
            if questions[target_idx].qid in visited:
                _log_nav_guard(len(visited) + 1, "cycle")
                return None
            visited.add(question.qid)
            next_index = target_idx
            idx = target_idx
            triggered = True
            break
        if not triggered:
            break
        hops += 1
    if hops >= MAX_NAV_HOPS:
        _log_nav_guard(hops, "depth")
        return None
    return next_index


def _log_rule_error(qid: str, directive: str, reason: str, detail: str) -> None:
    log.warning("rules error • qid=%s • directive=%s • reason=%s • detail=%s", qid, directive, reason, detail)
    if diag.is_enabled():
        diag.log_event_sync(
            "warning",
            "rules.error",
            qid=qid,
            directive=directive,
            reason=reason,
            detail=detail,
        )


def _log_flip(qid: str, before: QuestionState, after: QuestionState, directive: str) -> None:
    log.info(
        "rules flip • target=%s • from=%s • to=%s • by=%s",
        qid,
        before.humanized(),
        after.humanized(),
        directive,
    )
    if diag.is_enabled():
        diag.log_event_sync(
            "info",
            "rules.flip",
            target=qid,
            source_state=before.humanized(),
            target_state=after.humanized(),
            directive=directive,
        )


def _log_nav(source: str, target: str, directive: str) -> None:
    log.info("rules nav • from=%s • to=%s • reason=%s", source, target, directive)
    if diag.is_enabled():
        diag.log_event_sync(
            "info",
            "rules.nav",
            source=source,
            target=target,
            directive=directive,
        )


def _log_nav_guard(hops: int, reason: str) -> None:
    log.warning("rules nav_guard • hops=%s • reason=%s", hops, reason)
    if diag.is_enabled():
        diag.log_event_sync(
            "warning",
            "rules.nav_guard",
            hops=hops,
            reason=reason,
        )
