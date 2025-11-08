"""Reusable UI components for the onboarding wizard."""

from __future__ import annotations

import asyncio
import inspect
from typing import Callable, Optional

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


__all__ = ["AnswerModal", "BoolSelect"]

