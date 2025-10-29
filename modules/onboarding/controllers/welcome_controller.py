"""Controller for the sheet-driven onboarding welcome flow."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, Sequence

import discord
from discord.ext import commands

from modules.onboarding import rules
from modules.onboarding.session_store import SessionData, store
from modules.onboarding.ui.modal_renderer import build_modals
from modules.onboarding.ui.select_renderer import build_select_view
from shared.sheets.onboarding_questions import Question

log = logging.getLogger(__name__)

TEXT_TYPES = {"short", "paragraph", "number"}
SELECT_TYPES = {"single-select", "multi-select"}


class BaseWelcomeController:
    """Shared orchestration logic for welcome/promo onboarding flows."""

    def __init__(self, bot: commands.Bot, *, flow: str) -> None:
        self.bot = bot
        self.flow = flow
        self._threads: Dict[int, discord.Thread] = {}
        self._questions: Dict[int, list[Question]] = {}
        self._select_messages: Dict[int, discord.Message] = {}
        self._preview_messages: Dict[int, discord.Message] = {}
        self._preview_logged: set[int] = set()
        self._sources: Dict[int, str] = {}
        self._allowed_users: Dict[int, set[int]] = {}

    async def run(
        self,
        thread: discord.Thread,
        initiator: discord.abc.User | discord.Member | None,
        schema_hash: str | None,
        questions: Sequence[Question],
        *,
        source: str,
    ) -> None:
        thread_id = int(thread.id)
        session = store.ensure(thread_id, flow=self.flow, schema_hash=schema_hash)
        session.answers = session.answers or {}
        session.visibility = rules.evaluate_visibility(questions, session.answers)
        self._threads[thread_id] = thread
        self._questions[thread_id] = list(questions)
        self._sources[thread_id] = source
        store.register_timeout_callback(thread_id, self._handle_timeout)

        allowed_ids: set[int] = set()
        if initiator and getattr(initiator, "id", None):
            allowed_ids.add(int(initiator.id))
        owner_id = getattr(thread, "owner_id", None)
        if owner_id:
            allowed_ids.add(int(owner_id))
        if not allowed_ids and thread.guild is not None and thread.owner_id:
            allowed_ids.add(int(thread.owner_id))
        self._allowed_users[thread_id] = allowed_ids

        await self._start_modal_step(thread, session)

    async def _start_modal_step(self, thread: discord.Thread, session: SessionData) -> None:
        thread_id = int(thread.id)
        modals = build_modals(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        if not modals:
            await self._start_select_step(thread, session)
            return

        store.set_pending_step(thread_id, {"kind": "modal", "index": 0})
        intro = self._modal_intro_text()
        view = _ModalLauncherView(self, thread_id)
        await thread.send(intro, view=view)

    async def _start_select_step(self, thread: discord.Thread, session: SessionData) -> None:
        thread_id = int(thread.id)
        view = build_select_view(self._questions[thread_id], session.visibility, session.answers)
        if view is None:
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        store.set_pending_step(thread_id, {"kind": "select", "index": 0})
        content = self._select_intro_text()
        message = self._select_messages.get(thread_id)
        if message:
            await message.edit(content=content, view=view)
        else:
            message = await thread.send(content, view=view)
            self._select_messages[thread_id] = message

    def _select_changed(self, thread_id: int) -> Callable[[discord.Interaction, Question, list[str]], Awaitable[None]]:
        async def handler(
            interaction: discord.Interaction,
            question: Question,
            values: list[str],
        ) -> None:
            await self._handle_select_change(thread_id, interaction, question, values)

        return handler

    def _select_completed(self, thread_id: int) -> Callable[[discord.Interaction], Awaitable[None]]:
        async def handler(interaction: discord.Interaction) -> None:
            await self._handle_select_complete(thread_id, interaction)

        return handler

    async def _handle_modal_launch(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session is no longer active.")
            return

        modals = build_modals(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        pending = session.pending_step or {}
        index = int(pending.get("index", 0))
        if index >= len(modals):
            store.set_pending_step(thread_id, None)
            await _safe_ephemeral(interaction, "No more questions on this step.")
            await self._start_select_step(thread, session)
            return

        modal = modals[index]
        modal.submit_callback = self._modal_submitted(thread_id, modal.questions, index)
        store.set_pending_step(thread_id, {"kind": "modal", "index": index})
        await interaction.response.send_modal(modal)

    def _modal_submitted(
        self,
        thread_id: int,
        questions: Sequence[Question],
        index: int,
    ) -> Callable[[discord.Interaction, dict[str, str]], Awaitable[None]]:
        async def handler(
            interaction: discord.Interaction,
            values: dict[str, str],
        ) -> None:
            await self._handle_modal_submit(thread_id, interaction, questions, index, values)

        return handler

    async def _handle_modal_submit(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        questions: Sequence[Question],
        index: int,
        values: dict[str, str],
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session is no longer active.")
            return

        for question in questions:
            raw_value = values.get(question.qid, "")
            state = _visible_state(session.visibility, question.qid)
            required = bool(question.required) and state != "optional"
            answer = raw_value.strip()
            if question.type == "number":
                if not answer:
                    if required:
                        await _safe_ephemeral(
                            interaction,
                            f"⚠️ **{question.label}** is required.",
                        )
                        return
                    session.answers.pop(question.qid, None)
                    continue
                try:
                    parsed = int(answer)
                except ValueError:
                    await _safe_ephemeral(
                        interaction,
                        f"⚠️ **{question.label}** needs to be a whole number.",
                    )
                    return
                session.answers[question.qid] = parsed
                continue

            if required and not answer:
                await _safe_ephemeral(
                    interaction,
                    f"⚠️ **{question.label}** is required.",
                )
                return
            if answer:
                session.answers[question.qid] = answer
            else:
                session.answers.pop(question.qid, None)

        session.visibility = rules.evaluate_visibility(
            self._questions[thread_id],
            session.answers,
        )
        store.set_pending_step(thread_id, {"kind": "modal", "index": index + 1})
        await _safe_ephemeral(
            interaction,
            "✅ Saved! Use the button in the thread if more questions remain.",
        )

        modals = build_modals(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        if index + 1 >= len(modals):
            store.set_pending_step(thread_id, None)
            await self._start_select_step(thread, session)

    async def _handle_select_change(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        question: Question,
        values: list[str],
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        self._store_select_answer(session, question, values)
        session.visibility = rules.evaluate_visibility(
            self._questions[thread_id],
            session.answers,
        )
        store.set_pending_step(thread_id, session.pending_step)

        view = build_select_view(
            self._questions[thread_id],
            session.visibility,
            session.answers,
        )
        if view is None:
            store.set_pending_step(thread_id, None)
            await interaction.response.edit_message(view=None)
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        await interaction.response.edit_message(view=view)

    async def _handle_select_complete(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        missing = _missing_required_selects(
            self._questions[thread_id],
            session.visibility,
            session.answers,
        )
        if missing:
            labels = ", ".join(f"**{label}**" for label in missing)
            await _safe_ephemeral(
                interaction,
                f"⚠️ Please choose at least one option for {labels}.",
            )
            return

        store.set_pending_step(thread_id, None)
        await interaction.response.edit_message(view=None)
        await self._show_preview(thread, session)

    async def _show_preview(
        self,
        thread: discord.Thread,
        session: SessionData,
    ) -> None:
        thread_id = int(thread.id)
        embed = self._build_preview_embed(thread_id, session)
        view = _PreviewView(self, thread_id)
        message = self._preview_messages.get(thread_id)
        if message:
            await message.edit(embed=embed, view=view)
        else:
            message = await thread.send(embed=embed, view=view)
            self._preview_messages[thread_id] = message
        store.set_preview_message(
            thread_id,
            message_id=message.id,
            channel_id=getattr(message.channel, "id", None),
        )
        store.set_pending_step(thread_id, None)
        if thread_id not in self._preview_logged:
            self._preview_logged.add(thread_id)
            log.info(
                "onboarding.welcome.preview %s",
                {
                    "mode": self._sources.get(thread_id, "unknown"),
                    "flow": self.flow,
                    "thread_id": thread_id,
                    "schema_hash": session.schema_hash,
                },
            )

    def _build_preview_embed(self, thread_id: int, session: SessionData) -> discord.Embed:
        embed = discord.Embed(title="Review your responses")
        embed.description = "Confirm the information below before submitting."

        for question in self._questions.get(thread_id, []):
            state = _visible_state(session.visibility, question.qid)
            if state == "skip":
                continue
            value = _preview_value_for_question(question, session.answers.get(question.qid))
            if not value:
                value = "*(skipped)*"
            embed.add_field(name=question.label, value=value, inline=False)
        return embed

    async def _handle_confirm(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        summary_embed = self._build_summary_embed(thread_id, session)
        log.info(
            "onboarding.welcome.complete %s",
            {
                "mode": self._sources.get(thread_id, "unknown"),
                "flow": self.flow,
                "thread_id": thread_id,
                "schema_hash": session.schema_hash,
                "fields": _final_fields(self._questions[thread_id], session.answers),
            },
        )

        await interaction.response.edit_message(view=None)
        await thread.send(embed=summary_embed)
        store.set_preview_message(thread_id, message_id=None, channel_id=None)
        self._cleanup_session(thread_id)

    async def _handle_edit(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        await interaction.response.edit_message(view=None)
        await _safe_followup(
            interaction,
            "🛠️ Re-opening the form so you can make changes.",
        )
        await self._start_modal_step(thread, session)

    async def _handle_timeout(self, thread_id: int) -> None:
        thread = self._threads.get(thread_id)
        if thread is None:
            return
        preview = self._preview_messages.pop(thread_id, None)
        if preview is not None:
            try:
                await preview.delete()
            except Exception:
                try:
                    await preview.edit(view=None)
                except Exception:
                    log.warning("failed to remove preview on timeout", exc_info=True)
        select_message = self._select_messages.pop(thread_id, None)
        if select_message is not None:
            try:
                await select_message.edit(view=None)
            except Exception:
                log.warning("failed to disable select view on timeout", exc_info=True)
        store.set_preview_message(thread_id, message_id=None, channel_id=None)
        self._cleanup_session(thread_id)
        try:
            await thread.send("⏱️ Onboarding dialog timed out. Please react again to restart.")
        except Exception:
            log.warning("failed to send timeout message", exc_info=True)
        log.info(
            "onboarding.welcome.complete %s",
            {
                "flow": self.flow,
                "thread_id": thread_id,
                "cancelled": "timeout",
            },
        )

    def _cleanup_session(self, thread_id: int) -> None:
        store.end(thread_id)
        self._threads.pop(thread_id, None)
        self._questions.pop(thread_id, None)
        self._select_messages.pop(thread_id, None)
        self._preview_messages.pop(thread_id, None)
        self._sources.pop(thread_id, None)
        self._allowed_users.pop(thread_id, None)
        self._preview_logged.discard(thread_id)

    async def check_interaction(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> bool:
        allowed = self._allowed_users.get(thread_id)
        user_id = getattr(interaction.user, "id", None)
        if allowed and user_id not in allowed:
            await _safe_ephemeral(
                interaction,
                "⚠️ This dialog is reserved for the assigned recruiter.",
            )
            return False
        return True

    def _store_select_answer(
        self,
        session: SessionData,
        question: Question,
        values: Iterable[str],
    ) -> None:
        options = {option.value: option for option in question.options}
        if question.type == "single-select":
            if values:
                value = next(iter(values))
                option = options.get(value)
                if option:
                    session.answers[question.qid] = {
                        "value": option.value,
                        "label": option.label,
                    }
                else:
                    session.answers.pop(question.qid, None)
            else:
                session.answers.pop(question.qid, None)
            return

        selected: list[dict[str, str]] = []
        for token in values:
            option = options.get(token)
            if option:
                selected.append({"value": option.value, "label": option.label})
        if selected:
            session.answers[question.qid] = selected
        else:
            session.answers.pop(question.qid, None)

    def _modal_title_prefix(self) -> str:
        return "Onboarding questions"

    def _modal_intro_text(self) -> str:
        return "🧭 Let's capture some details. Press the button below to start."

    def _select_intro_text(self) -> str:
        return "🔽 Choose the options that apply using the menus below."

    def _build_summary_embed(self, thread_id: int, session: SessionData) -> discord.Embed:
        embed = discord.Embed(title="Thanks! Here's what we captured")
        for question in self._questions.get(thread_id, []):
            state = _visible_state(session.visibility, question.qid)
            if state == "skip":
                continue
            value = _preview_value_for_question(question, session.answers.get(question.qid))
            if not value:
                value = "*(skipped)*"
            embed.add_field(name=question.label, value=value, inline=False)
        return embed


class WelcomeController(BaseWelcomeController):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot, flow="welcome")


class _ModalLauncherView(discord.ui.View):
    def __init__(self, controller: BaseWelcomeController, thread_id: int) -> None:
        super().__init__(timeout=600)
        self.controller = controller
        self.thread_id = thread_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - network
        return await self.controller.check_interaction(self.thread_id, interaction)

    @discord.ui.button(
        label="Open questions",
        style=discord.ButtonStyle.primary,
        custom_id="ob.modal.open",
    )
    async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        await self.controller._handle_modal_launch(self.thread_id, interaction)

    async def on_timeout(self) -> None:  # pragma: no cover - network
        for child in self.children:
            child.disabled = True


class _PreviewView(discord.ui.View):
    def __init__(self, controller: BaseWelcomeController, thread_id: int) -> None:
        super().__init__(timeout=600)
        self.controller = controller
        self.thread_id = thread_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - network
        return await self.controller.check_interaction(self.thread_id, interaction)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="ob.confirm")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        await self.controller._handle_confirm(self.thread_id, interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, custom_id="ob.edit")
    async def edit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        await self.controller._handle_edit(self.thread_id, interaction)

    async def on_timeout(self) -> None:  # pragma: no cover - network
        for child in self.children:
            child.disabled = True


async def _safe_ephemeral(interaction: discord.Interaction, message: str) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception:  # pragma: no cover - defensive network handling
        log.warning("failed to send ephemeral response", exc_info=True)


def _visible_state(visibility: dict[str, dict[str, str]], qid: str) -> str:
    return visibility.get(qid, {}).get("state", "show")


def _preview_value_for_question(question: Question, stored: Any) -> str:
    if stored is None:
        return ""
    if question.type in TEXT_TYPES:
        return str(stored)
    if question.type == "single-select":
        if isinstance(stored, dict):
            label = stored.get("label") or stored.get("value")
            return str(label or "")
        return str(stored)
    if isinstance(stored, Iterable):
        labels = []
        for item in stored:
            if isinstance(item, dict):
                label = item.get("label") or item.get("value")
                if label:
                    labels.append(str(label))
            else:
                labels.append(str(item))
        return ", ".join(labels)
    return str(stored)


def _missing_required_selects(
    questions: Sequence[Question],
    visibility: dict[str, dict[str, str]],
    answers: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    for question in questions:
        if question.type not in SELECT_TYPES:
            continue
        state = _visible_state(visibility, question.qid)
        if state == "skip":
            continue
        required = bool(question.required) and state != "optional"
        if not required:
            continue
        value = answers.get(question.qid)
        if not _has_select_answer(value):
            missing.append(question.label)
    return missing


def _has_select_answer(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        if value.get("value"):
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


def _final_fields(questions: Sequence[Question], answers: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    option_lookup: dict[str, dict[str, str]] = {}
    for question in questions:
        if question.type in SELECT_TYPES:
            option_lookup[question.qid] = {option.value: option.label for option in question.options}
    for qid, value in answers.items():
        label_value = _convert_to_labels(value, option_lookup.get(qid, {}))
        if isinstance(label_value, str) and len(label_value) > 300:
            label_value = label_value[:297] + "..."
        fields[qid] = label_value
    return fields


def _convert_to_labels(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        if "value" in value:
            token = value.get("value")
            return mapping.get(token, str(value.get("label") or token))
        if "values" in value:
            items = value.get("values")
            if isinstance(items, Iterable):
                return [
                    mapping.get(item.get("value"), item.get("label"))
                    if isinstance(item, dict)
                    else mapping.get(str(item), str(item))
                    for item in items
                ]
        return {key: _convert_to_labels(val, mapping) for key, val in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [_convert_to_labels(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def _safe_followup(interaction: discord.Interaction, message: str) -> Awaitable[None]:
    async def runner() -> None:
        try:
            await interaction.followup.send(message, ephemeral=True)
        except Exception:
            log.warning("failed to send follow-up", exc_info=True)

    return runner()


__all__ = ["WelcomeController", "BaseWelcomeController"]
