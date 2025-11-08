"""Rendering helpers for Inputs v1 onboarding questions."""

from __future__ import annotations

from typing import Tuple

import discord

from modules.onboarding.ui.components import AnswerModal, BoolSelect

GUIDANCE = "Use the buttons below. Don’t type answers as messages—those won’t be read."


def _answer_chip(value) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    return text if len(text) <= 120 else f"{text[:117]}…"


def build_view(
    controller,
    session,
    question,
    *,
    required: bool,
    has_answer: bool,
    optional: bool,
) -> Tuple[str, discord.ui.View]:
    """Return ``(content, view)`` for the onboarding wizard panel."""

    req_txt = "(required)" if required else "(optional)"
    title = f"**{question['label']}** {req_txt}"
    help_text = question.get("help") or ""
    help_line = f"_{help_text}_" if help_text else ""
    current = session.answers.get(question["gid"])
    chip = f"💬 Current answer: {_answer_chip(current)}"

    lines = [GUIDANCE, "", title]
    if help_line:
        lines.append(help_line)
    lines.extend(["", chip, ""])
    content = "\n".join(lines)

    qtype = question["type"]

    if qtype == "bool":
        async def _handle_bool(interaction: discord.Interaction, value: bool):
            await controller._save_bool_answer(interaction, session, question, value)

        view: discord.ui.View = BoolSelect(
            lambda interaction: controller._async_spawn(_handle_bool(interaction, True)),
            lambda interaction: controller._async_spawn(_handle_bool(interaction, False)),
        )
    else:
        view = discord.ui.View(timeout=180)

    if qtype in {"short", "number", "paragraph"}:

        async def _handle_submit(interaction: discord.Interaction, value: str):
            await controller._save_modal_answer(interaction, session, question, value)

        async def _launch_modal(interaction: discord.Interaction) -> None:
            modal = AnswerModal(
                question,
                lambda modal_interaction, value: controller._async_spawn(
                    _handle_submit(modal_interaction, value)
                ),
            )
            await interaction.response.send_modal(modal)

        answer_button = discord.ui.Button(
            label="Answer",
            style=discord.ButtonStyle.primary,
            custom_id=f"answer_{question['gid']}",
        )

        async def _answer_callback(interaction: discord.Interaction) -> None:
            await _launch_modal(interaction)

        answer_button.callback = _answer_callback  # type: ignore[assignment]
        view.add_item(answer_button)

    # Navigation buttons (shared across question types)
    back_button = discord.ui.Button(
        label="Back",
        style=discord.ButtonStyle.secondary,
        custom_id="nav_back",
    )

    async def _back_callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer_update()
        await controller.back(interaction, session)

    back_button.callback = _back_callback  # type: ignore[assignment]
    view.add_item(back_button)

    if optional:
        skip_button = discord.ui.Button(
            label="Skip",
            style=discord.ButtonStyle.secondary,
            custom_id="nav_skip",
        )

        async def _skip_callback(interaction: discord.Interaction) -> None:
            await interaction.response.defer_update()
            await controller.skip(interaction, session, question)

        skip_button.callback = _skip_callback  # type: ignore[assignment]
        view.add_item(skip_button)

    next_button = discord.ui.Button(
        label="Next",
        style=discord.ButtonStyle.primary,
        custom_id="nav_next",
        disabled=required and not has_answer,
    )

    async def _next_callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer_update()
        await controller.next(interaction, session)

    next_button.callback = _next_callback  # type: ignore[assignment]
    view.add_item(next_button)

    cancel_button = discord.ui.Button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        custom_id="nav_cancel",
    )

    async def _cancel_callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer_update()
        await controller.cancel(interaction, session)

    cancel_button.callback = _cancel_callback  # type: ignore[assignment]
    view.add_item(cancel_button)

    return content, view


__all__ = ["GUIDANCE", "build_view"]

