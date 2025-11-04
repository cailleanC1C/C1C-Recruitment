"""Rules evaluator for onboarding question visibility."""

from __future__ import annotations

import re
from collections.abc import Iterable as IterableABC, Mapping as MappingABC, Sequence as SequenceABC
from typing import Any, Dict, List, Optional

from shared.sheets.onboarding_questions import Question

VisibilityState = Dict[str, Dict[str, str]]

_SKIP_PRIORITY = {"show": 0, "optional": 1, "skip": 2}

_OPTIONAL_ACTION = "optional"
_SKIP_ACTION = "skip"


def evaluate_visibility(
    questions: SequenceABC[Question],
    answers: MappingABC[str, Any],
) -> VisibilityState:
    """Return a visibility map derived from ``questions`` and ``answers``."""

    states: VisibilityState = {question.qid: {"state": "show"} for question in questions}
    answer_tokens_by_qid = _collect_answer_tokens_by_qid(answers)
    if not answer_tokens_by_qid:
        return states

    order_map = _build_order_map(questions)
    qid_lookup = {question.qid.lower(): question.qid for question in questions}

    for question in questions:
        if not question.rules:
            continue
        qid_key = question.qid
        question_tokens = answer_tokens_by_qid.get(qid_key) or answer_tokens_by_qid.get(qid_key.lower())
        if not question_tokens:
            continue
        for condition, action, targets in _parse_rules(question.rules):
            condition_tokens = _normalise_token_variants(condition)
            if not question_tokens.intersection(condition_tokens):
                continue
            qids = _resolve_targets(targets, qid_lookup, order_map)
            for qid in qids:
                _apply_action(states, qid, action)
    return states


def _collect_answer_tokens_by_qid(answers: MappingABC[str, Any]) -> Dict[str, set[str]]:
    tokens_by_qid: Dict[str, set[str]] = {}
    for key, value in answers.items():
        tokens = _collect_answer_tokens(value)
        if not tokens:
            continue
        tokens_by_qid[key] = tokens
        tokens_by_qid.setdefault(key.lower(), tokens)
    return tokens_by_qid


def _collect_answer_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if value is None:
        return tokens
    if isinstance(value, str):
        tokens.update(_normalise_token_variants(value))
    elif isinstance(value, MappingABC):
        for nested in value.values():
            tokens.update(_collect_answer_tokens(nested))
    elif isinstance(value, IterableABC):
        if isinstance(value, (bytes, bytearray)):
            tokens.update(_normalise_token_variants(value.decode()))
        else:
            for item in value:
                tokens.update(_collect_answer_tokens(item))
    else:
        tokens.update(_normalise_token_variants(str(value)))
    return {token for token in tokens if token}


def _normalise_token_variants(value: str) -> set[str]:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return set()
    variants = {text}
    variants.add(text.replace("-", " "))
    variants.add(text.replace("_", " "))
    return {variant for variant in variants if variant}


def _build_order_map(questions: SequenceABC[Question]) -> Dict[str, list[str]]:
    mapping: Dict[str, list[str]] = {}
    for question in questions:
        order_key = question.order.strip().lower()
        if not order_key:
            continue
        mapping.setdefault(order_key, []).append(question.qid)
    return mapping


def _parse_rules(rules: str) -> list[tuple[str, str, list[str]]]:
    pieces = re.split(r"[\n;]+", rules)
    parsed: list[tuple[str, str, list[str]]] = []
    for piece in pieces:
        clause = " ".join(piece.strip().lower().split())
        if not clause:
            continue
        match = re.match(r"^if\s+(?P<cond>.+?)\s+(?P<verb>skip|make)\s+(?P<rest>.+)$", clause)
        if not match:
            continue
        cond = match.group("cond").strip()
        verb = match.group("verb")
        rest = match.group("rest").strip()
        action = _SKIP_ACTION
        if verb == "make":
            if rest.endswith(" optional"):
                rest = rest[: -len(" optional")].strip()
            action = _OPTIONAL_ACTION
        targets = _split_targets(rest)
        if cond and action and targets:
            parsed.append((cond, action, targets))
    return parsed


def _split_targets(text: str) -> list[str]:
    cleaned = text.replace(" and ", ",")
    cleaned = cleaned.replace("&", ",")
    tokens = [token.strip() for token in cleaned.split(",")]
    return [token for token in tokens if token]


def _resolve_targets(
    targets: SequenceABC[str],
    qid_lookup: MappingABC[str, str],
    order_map: MappingABC[str, SequenceABC[str]],
) -> set[str]:
    resolved: set[str] = set()
    for target in targets:
        normalized = target.strip().lower().rstrip(".")
        if not normalized:
            continue
        if normalized.endswith("*"):
            base = normalized[:-1]
            for order_key, qids in order_map.items():
                if order_key.startswith(base):
                    resolved.update(qids)
            continue
        if normalized in order_map:
            resolved.update(order_map[normalized])
            continue
        qid = qid_lookup.get(normalized)
        if qid:
            resolved.add(qid)
    return resolved


def _apply_action(states: VisibilityState, qid: str, action: str) -> None:
    if qid not in states:
        return
    current = states[qid]["state"]
    if action == _SKIP_ACTION:
        states[qid]["state"] = _SKIP_ACTION
        return
    if action == _OPTIONAL_ACTION and _SKIP_PRIORITY[current] < _SKIP_PRIORITY[_OPTIONAL_ACTION]:
        states[qid]["state"] = _OPTIONAL_ACTION


_COND_RE = re.compile(
    r"^if\s+(?P<qid>[A-Za-z0-9_]+)\s+(?P<op>in|=|!=|<=|>=|<|>)\s+(?P<rhs>.+?)(?:\s+goto\s+(?P<goto>[0-9]+[A-Za-z]?))?(?:\s+else\s+goto\s+(?P<goto_else>[0-9]+[A-Za-z]?))?$",
    re.IGNORECASE,
)

_RANGE_SKIP_RE = re.compile(
    r"^skip\s+order>=(?P<lo>[0-9]+)\s+and\s+order<(?P<hi>[0-9]+)$",
    re.IGNORECASE,
)


def _norm(value: Any) -> str:
    """Normalize values to trimmed strings for comparison."""

    return str(value).strip()


def _parse_rhs_list(text: str) -> list[str]:
    """Accept '[A, B]' or 'A,B' → ['A','B'] (trimmed)."""

    cleaned = (text or "").strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    return [token.strip() for token in cleaned.split(",") if token.strip()]


def next_index_by_rules(
    current_idx: int, questions: List[Any], answers_by_qid: Dict[str, Any]
) -> Optional[int]:
    """Return the absolute index to jump to based on the sheet rule, if any."""

    if current_idx < 0 or current_idx >= len(questions):
        return None
    question = questions[current_idx]
    rule = str(getattr(question, "rules", "") or "").strip()
    if not rule:
        return None

    if rule.lower().startswith("skip "):
        if _RANGE_SKIP_RE.match(rule):
            return None

    match = _COND_RE.match(rule)
    if not match:
        return None

    qid = match.group("qid")
    op = match.group("op").lower()
    rhs = match.group("rhs")
    goto = match.group("goto")
    goto_else = match.group("goto_else")

    if not qid:
        return None

    value = answers_by_qid.get(qid) or answers_by_qid.get(qid.lower())
    if value is None:
        return None

    candidates = _candidate_tokens(value)
    if not candidates:
        return None

    if _condition_satisfied(op, candidates, rhs):
        return _index_for_order(questions, goto)
    return _index_for_order(questions, goto_else)


def _candidate_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, MappingABC):
        tokens: list[str] = []
        label = value.get("label") or value.get("value")
        if isinstance(label, str) and label.strip():
            tokens.append(label.strip())
        nested = value.get("values")
        if isinstance(nested, IterableABC):
            tokens.extend(_candidate_tokens(list(nested)))
        return tokens
    if isinstance(value, IterableABC) and not isinstance(value, (bytes, bytearray)):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_candidate_tokens(item))
        return tokens
    text = str(value).strip()
    return [text] if text else []


def _condition_satisfied(op: str, candidates: list[str], rhs: str) -> bool:
    try:
        if op == "in":
            options = _parse_rhs_list(rhs)
            return any(candidate in options for candidate in candidates)

        rhs_token = _norm(rhs)
        if op == "=":
            return any(candidate == rhs_token for candidate in candidates)
        if op == "!=":
            return all(candidate != rhs_token for candidate in candidates)

        rhs_value = float(rhs_token)
        for candidate in candidates:
            try:
                value = float(candidate)
            except Exception:
                continue
            if op == "<" and value < rhs_value:
                return True
            if op == "<=" and value <= rhs_value:
                return True
            if op == ">" and value > rhs_value:
                return True
            if op == ">=" and value >= rhs_value:
                return True
        return False
    except Exception:
        return False


def _index_for_order(questions: List[Any], order_token: Optional[str]) -> Optional[int]:
    if not order_token:
        return None
    needle = str(order_token).strip().lower()
    if not needle:
        return None
    for index, question in enumerate(questions):
        order_value = getattr(question, "order_raw", None)
        if order_value is None:
            order_value = getattr(question, "order", None)
        if order_value is None:
            continue
        if str(order_value).strip().lower() == needle:
            return index
    return None
