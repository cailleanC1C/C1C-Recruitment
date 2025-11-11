"""Server-side helpers for onboarding submission validation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from shared.sheets.onboarding_questions import Question

_SELECT_TYPES = {"single-select", "multi-select"}


def missing_required_questions(
    questions: Sequence[Question],
    visibility: Mapping[str, Mapping[str, Any]],
    answers: Mapping[str, Any],
) -> list[Question]:
    missing: list[Question] = []
    for question in questions:
        state = (visibility.get(question.qid) or {}).get("state", "show")
        if state == "skip":
            continue
        required = _is_required(question, visibility)
        if not required:
            continue
        value = answers.get(question.qid)
        if not _has_answer(question, value):
            missing.append(question)
    return missing


def _is_required(question: Question, visibility: Mapping[str, Mapping[str, Any]]) -> bool:
    info = visibility.get(question.qid) or {}
    if "required" in info:
        return bool(info["required"])
    if info.get("state") == "optional":
        return False
    return bool(getattr(question, "required", False))


def _has_answer(question: Question, value: Any) -> bool:
    if question.type in _SELECT_TYPES:
        return _has_select_answer(value)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return True
    return True


def _has_select_answer(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        if isinstance(value.get("value"), str) and value.get("value").strip():
            return True
        nested = value.get("values")
        if isinstance(nested, Iterable):
            return any(_has_select_answer(item) for item in nested)
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return any(_has_select_answer(item) for item in value)
    return bool(value)


__all__ = ["missing_required_questions"]
