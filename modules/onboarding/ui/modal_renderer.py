"""Helpers to build Discord modals for onboarding questions."""

from __future__ import annotations

from typing import Awaitable, Callable, Sequence

import discord

from shared.sheets.onboarding_questions import Question

TEXT_TYPES = {"short", "paragraph", "number"}


class WelcomeQuestionnaireModal(discord.ui.Modal):
    """Modal that renders a slice of onboarding questions."""

    def __init__(
        self,
        *,
        questions: Sequence[Question],
        step_index: int,
        total_steps: int,
        title_prefix: str = "Onboarding",
        answers: dict[str, object] | None = None,
        visibility: dict[str, dict[str, str]] | None = None,
        on_submit: Callable[[discord.Interaction, dict[str, str]], Awaitable[None]] | None = None,
    ) -> None:
        title = f"{title_prefix} ({step_index + 1}/{max(total_steps, 1)})"
        super().__init__(title=title, timeout=600)
        self.questions = list(questions)
        self.step_index = step_index
        self.total_steps = total_steps
        self.answers = answers or {}
        self.visibility = visibility or {}
        self.submit_callback = on_submit

        for question in self.questions:
            default = _coerce_answer_to_default(self.answers.get(question.qid))
            state = _visible_state(self.visibility, question.qid)
            required = _is_required(question, self.visibility)
            text_input = discord.ui.TextInput(
                label=question.label,
                custom_id=question.qid,
                placeholder=question.help or None,
                style=(
                    discord.TextStyle.long
                    if question.type == "paragraph"
                    else discord.TextStyle.short
                ),
                default=default,
                required=required,
                max_length=question.maxlen or None,
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # pragma: no cover - event handler
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass
        payload: dict[str, str] = {}
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                payload[child.custom_id] = child.value
        if self.submit_callback is not None:
            await self.submit_callback(interaction, payload)


def build_modals(
    questions: Sequence[Question],
    visibility: dict[str, dict[str, str]],
    answers: dict[str, object] | None,
    *,
    title_prefix: str = "Onboarding",
) -> list[WelcomeQuestionnaireModal]:
    """Return modal pages for the visible text/number questions."""

    relevant = [
        question
        for question in questions
        if question.type in TEXT_TYPES
        and _visible_state(visibility, question.qid) != "skip"
    ]
    if not relevant:
        return []
    grouped = _chunk(relevant, 5)
    total = len(grouped)
    modals: list[WelcomeQuestionnaireModal] = []
    for idx, chunk in enumerate(grouped):
        modal = WelcomeQuestionnaireModal(
            questions=chunk,
            step_index=idx,
            total_steps=total,
            title_prefix=title_prefix,
            answers=answers or {},
            visibility=visibility,
        )
        modals.append(modal)
    return modals


def _chunk(items: Sequence[Question], size: int) -> list[list[Question]]:
    grouped: list[list[Question]] = []
    for question in items:
        if not grouped or len(grouped[-1]) >= size:
            grouped.append([])
        grouped[-1].append(question)
    return grouped


def _visible_state(visibility: dict[str, dict[str, str]], qid: str) -> str:
    state = visibility.get(qid, {}).get("state")
    return state or "show"


def _is_required(question: Question, visibility: dict[str, dict[str, str]]) -> bool:
    info = visibility.get(question.qid) or {}
    if "required" in info:
        return bool(info["required"])
    if info.get("state") == "optional":
        return False
    return bool(question.required)


def _coerce_answer_to_default(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:  # pragma: no cover - defensive
        return None


__all__ = ["WelcomeQuestionnaireModal", "build_modals"]

