"""UI helpers to render onboarding select questions as Discord components."""

from __future__ import annotations

from typing import Awaitable, Callable, Iterable, Sequence

import discord

from modules.onboarding import logs

from shared.sheets.onboarding_questions import Question

SelectChangeCallback = Callable[[discord.Interaction, Question, list[str]], Awaitable[None]]
SelectCompleteCallback = Callable[[discord.Interaction], Awaitable[None]]
InteractionGate = Callable[[discord.Interaction], Awaitable[bool]]


class SelectQuestionView(discord.ui.View):
    """Discord view rendering onboarding single/multi-select questions."""

    def __init__(
        self,
        *,
        questions: Sequence[Question],
        visibility: dict[str, dict[str, str]],
        answers: dict[str, object] | None = None,
        timeout: float = 600,
        interaction_check: InteractionGate | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.questions = [
            question
            for question in questions
            if question.type in {"single-select", "multi-select"}
            and _visible_state(visibility, question.qid) != "skip"
        ]
        self.visibility = visibility
        self.answers = answers or {}
        self.on_change: SelectChangeCallback | None = None
        self.on_complete: SelectCompleteCallback | None = None
        self._interaction_gate = interaction_check

        for question in self.questions:
            select = _QuestionSelect(question, visibility, self.answers)
            self.add_item(select)
        if self.questions:
            self.add_item(_SelectContinueButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - requires Discord
        if self._interaction_gate is None:
            return True
        return await self._interaction_gate(interaction)

    async def handle_change(
        self,
        interaction: discord.Interaction,
        question: Question,
        values: list[str],
    ) -> None:
        if self.on_change is not None:
            await self.on_change(interaction, question, values)

    async def handle_complete(self, interaction: discord.Interaction) -> None:
        if self.on_complete is not None:
            await self.on_complete(interaction)


class _QuestionSelect(discord.ui.Select):
    def __init__(
        self,
        question: Question,
        visibility: dict[str, dict[str, str]],
        answers: dict[str, object],
    ) -> None:
        self.question = question
        self.visibility = visibility
        existing = _extract_existing_tokens(question, answers.get(question.qid))
        min_values = 1 if question.required and _visible_state(visibility, question.qid) != "optional" else 0
        max_values = _resolve_max_values(question)
        options = [
            discord.SelectOption(label=option.label, value=option.value, default=option.value in existing)
            for option in question.options
        ]
        placeholder = question.help or question.label
        custom_id = f"ob.select.{question.qid}"
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - requires Discord
        view: SelectQuestionView | None = self.view  # type: ignore[assignment]
        if view is not None:
            await view.handle_change(interaction, self.question, list(self.values))


class _SelectContinueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Continue",
            style=discord.ButtonStyle.primary,
            custom_id="ob.select.confirm",
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - requires Discord
        if not _claim_interaction(interaction):
            return
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        context = {
            **logs.thread_context(thread if isinstance(thread, discord.Thread) else None),
            "actor": logs.format_actor(interaction.user),
            "view": "select",
            "view_id": self.custom_id,
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            context["actor_name"] = actor_name
        await logs.send_welcome_log("debug", result="clicked", **context)
        view: SelectQuestionView | None = self.view  # type: ignore[assignment]
        if view is not None:
            await view.handle_complete(interaction)


def build_select_view(
    questions: Sequence[Question],
    visibility: dict[str, dict[str, str]],
    answers: dict[str, object] | None,
    *,
    interaction_check: InteractionGate | None = None,
) -> SelectQuestionView | None:
    """Return a view configured for the visible select questions."""

    view = SelectQuestionView(
        questions=questions,
        visibility=visibility,
        answers=answers or {},
        interaction_check=interaction_check,
    )
    if not view.questions:
        return None
    return view


def _extract_existing_tokens(question: Question, stored: object | None) -> set[str]:
    if stored is None:
        return set()
    tokens: set[str] = set()
    if isinstance(stored, str):
        tokens.add(stored)
    elif isinstance(stored, dict):
        value = stored.get("value")
        if isinstance(value, str):
            tokens.add(value)
        values = stored.get("values")
        if isinstance(values, Iterable):
            for item in values:
                if isinstance(item, dict):
                    token = item.get("value")
                    if isinstance(token, str):
                        tokens.add(token)
    elif isinstance(stored, Iterable):
        for item in stored:
            if isinstance(item, str):
                tokens.add(item)
            elif isinstance(item, dict):
                token = item.get("value")
                if isinstance(token, str):
                    tokens.add(token)
    return tokens


def _visible_state(visibility: dict[str, dict[str, str]], qid: str) -> str:
    state = visibility.get(qid, {}).get("state")
    return state or "show"


def _resolve_max_values(question: Question) -> int:
    if question.type == "single-select":
        return 1
    if question.multi_max is not None and question.multi_max > 0:
        return question.multi_max
    return max(1, len(question.options))


__all__ = [
    "SelectQuestionView",
    "build_select_view",
]

def _claim_interaction(interaction: discord.Interaction) -> bool:
    if getattr(interaction, "_c1c_claimed", False):
        return False
    setattr(interaction, "_c1c_claimed", True)
    return True
