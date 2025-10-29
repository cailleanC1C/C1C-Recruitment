"""Rules evaluator for onboarding question visibility."""

from __future__ import annotations

import re
from collections.abc import Iterable as IterableABC, Mapping as MappingABC, Sequence as SequenceABC
from typing import Any, Dict

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
