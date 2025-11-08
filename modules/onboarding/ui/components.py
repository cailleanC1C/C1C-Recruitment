"""Reusable UI components for the onboarding wizard."""

from __future__ import annotations

import asyncio
import inspect
from typing import Callable, List, Optional, Sequence

import discord


class AnswerModal(discord.ui.Modal, title="Answer"):
    """Modal surface for text, number, or paragraph answers."""

    def __init__(
        self, question: dict, on_submit_cb: Callable[[discord.Interaction, str], None]
    ) -> None:
        super().__init__(timeout=180)
        self.question = question
        self._on_submit_cb = on_submit_cb
        maxlen = int(question.get("maxlen") or 4000)
        style = (
            discord.TextStyle.paragraph
            if question.get("type") == "paragraph"
            else discord.TextStyle.short
        )
        self.input = discord.ui.TextInput(
            label=question.get("label") or "Answer",
            placeholder=question.get("help") or "",
            max_length=maxlen,
            style=style,
            required=True,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = str(self.input.value).strip()
        await interaction.response.defer()
        self._on_submit_cb(interaction, value)


class BoolSelect(discord.ui.View):
    """Yes/No button pair for boolean questions."""

    def __init__(
        self,
        on_yes: Callable[[discord.Interaction], Optional[object]],
        on_no: Callable[[discord.Interaction], Optional[object]],
        *,
        timeout: Optional[float] = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self._on_yes = on_yes
        self._on_no = on_no

    def _run_callback(
        self, callback: Callable[[discord.Interaction], Optional[object]], interaction: discord.Interaction
    ) -> None:
        try:
            result = callback(interaction)
            if inspect.isawaitable(result):
                # Fire and forget – follow-up handled by controller.
                loop = getattr(getattr(interaction, "client", None), "loop", None)
                if loop and loop.is_running():
                    loop.create_task(result)
                else:
                    asyncio.create_task(result)
        except Exception:
            # Controllers handle logging; we intentionally swallow to keep UI responsive.
            pass

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success, custom_id="q_bool_yes")
    async def yes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:  # pragma: no cover - callback
        await interaction.response.defer_update()
        self._run_callback(self._on_yes, interaction)

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger, custom_id="q_bool_no")
    async def no(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:  # pragma: no cover - callback
        await interaction.response.defer_update()
        self._run_callback(self._on_no, interaction)


def _mk_options(values: Sequence[str]) -> List[discord.SelectOption]:
    return [discord.SelectOption(label=v, value=v) for v in values]


class SingleSelectView(discord.ui.View):
    def __init__(
        self,
        values: Sequence[str],
        preselect: str | None,
        on_pick: Callable[[discord.Interaction, str], None],
        *,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        opts = _mk_options(values)
        self.select = discord.ui.Select(
            placeholder="Choose one…",
            options=opts,
            min_values=1,
            max_values=1,
            custom_id="q_single_select",
        )
        if preselect and preselect in values:
            self.select.default_values = [preselect]

        async def _changed(inter: discord.Interaction):
            await inter.response.defer_update()
            on_pick(inter, self.select.values[0])

        self.select.callback = _changed
        self.add_item(self.select)


class MultiSelectView(discord.ui.View):
    def __init__(
        self,
        values: Sequence[str],
        preselect: Sequence[str],
        on_pick: Callable[[discord.Interaction, List[str]], None],
        *,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        opts = _mk_options(values)
        self.select = discord.ui.Select(
            placeholder="Choose one or more…",
            options=opts,
            min_values=1,
            max_values=max(1, len(values)),
            custom_id="q_multi_select",
        )
        if preselect:
            self.select.default_values = [v for v in preselect if v in values]

        async def _changed(inter: discord.Interaction):
            await inter.response.defer_update()
            on_pick(inter, list(self.select.values))

        self.select.callback = _changed
        self.add_item(self.select)


__all__ = [
    "AnswerModal",
    "BoolSelect",
    "MultiSelectView",
    "SingleSelectView",
]

