"""Helpers for mapping onboarding questions into UI buckets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from shared.sheets.onboarding_questions import Question

ModalCap = 5


class SplitResult(TypedDict):
    modal: list[Question]
    select: list[Question]
    modal_overflow: int


def split_by_input_mode(questions: Sequence[Question]) -> SplitResult:
    """Group questions into modal and select input groups."""

    modal_types = {"short", "paragraph", "number"}
    select_types = {"single-select", "multi-select"}

    modal: list[Question] = []
    select: list[Question] = []

    for question in questions:
        if question.type in modal_types:
            modal.append(question)
        elif question.type in select_types:
            select.append(question)
        else:
            raise ValueError(f"Unsupported question type for split: {question.type}")

    overflow = 0
    if len(modal) > ModalCap:
        overflow = len(modal) - ModalCap
        modal = modal[:ModalCap]

    return SplitResult(modal=modal, select=select, modal_overflow=overflow)
