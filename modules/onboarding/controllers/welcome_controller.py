"""Controller for the sheet-driven onboarding welcome flow."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable, Dict, Iterable, Sequence, cast

import discord
from discord.ext import commands

from modules.onboarding import diag, logs, rules
from modules.onboarding.session_store import SessionData, store
from modules.onboarding.ui.modal_renderer import WelcomeQuestionnaireModal, build_modals
from modules.onboarding.ui.select_renderer import build_select_view
from modules.onboarding.ui.summary_embed import build_summary_embed
from modules.onboarding.ui import panels
from shared.sheets.onboarding_questions import Question

log = logging.getLogger(__name__)
gate_log = logging.getLogger("c1c.onboarding.gate")


def _display_name(user: discord.abc.User | discord.Member | None) -> str:
    if user is None:
        return "<unknown>"
    return (
        getattr(user, "display_name", None)
        or getattr(user, "global_name", None)
        or getattr(user, "name", None)
        or "<unknown>"
    )


def _channel_path(channel: discord.abc.GuildChannel | discord.Thread | None) -> str:
    if isinstance(channel, discord.Thread):
        parent = getattr(channel, "parent", None)
        parent_label = f"#{getattr(parent, 'name', 'unknown')}" if parent else "#unknown"
        return f"{parent_label} › {getattr(channel, 'name', 'thread')}"
    if isinstance(channel, discord.abc.GuildChannel):
        return f"#{getattr(channel, 'name', 'channel')}"
    return "#unknown"


def _log_gate(
    interaction: discord.Interaction,
    *,
    allowed: bool,
    reason: str,
    fallback_thread: discord.Thread | None = None,
) -> None:
    channel_obj: discord.abc.GuildChannel | discord.Thread | None
    channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else fallback_thread
    emoji = "✅" if allowed else "🔐"
    status = "ok" if allowed else "deny"
    gate_log.info(
        "%s Welcome — gate=%s • user=%s • channel=%s • reason=%s",
        emoji,
        status,
        _display_name(getattr(interaction, "user", None)),
        _channel_path(channel_obj),
        reason,
    )


def _log_followup_fallback(
    interaction: discord.Interaction,
    *,
    action: str,
    error: Exception,
) -> None:
    gate_log.warning(
        "⚠️ Welcome — followup fallback • action=%s • user=%s • channel=%s • why=%s",
        action,
        _display_name(getattr(interaction, "user", None)),
        _channel_path(getattr(interaction, "channel", None)),
        getattr(error, "__class__", type(error)).__name__,
    )


async def _edit_deferred_response(interaction: discord.Interaction, message: str) -> None:
    try:
        await interaction.edit_original_response(content=message)
    except Exception as exc:  # pragma: no cover - defensive fallback
        _log_followup_fallback(interaction, action="edit_original", error=exc)
        followup = getattr(interaction, "followup", None)
        if followup is None:
            log.debug("followup handler missing; skipping deferred notice")
            return
        try:
            await followup.send(message, ephemeral=True)
        except Exception:  # pragma: no cover - final guard
            log.warning("failed to deliver followup message", exc_info=True)

_PANEL_RETRY_DELAYS = (0.5, 1.0, 2.0)

TEXT_TYPES = {"short", "paragraph", "number"}
SELECT_TYPES = {"single-select", "multi-select"}


async def locate_welcome_message(thread: discord.Thread) -> discord.Message | None:
    """Return the welcome greeting message for ``thread`` when available."""

    starter = getattr(thread, "starter_message", None)
    if starter is not None:
        return starter

    parent = getattr(thread, "parent", None)
    if parent is not None:
        parent_fetch = getattr(parent, "fetch_message", None)
        if callable(parent_fetch):
            try:
                return await parent_fetch(int(thread.id))
            except Exception:
                pass

    history = getattr(thread, "history", None)
    if callable(history):
        try:
            async for candidate in history(limit=5, oldest_first=True):
                return candidate
        except Exception:
            pass

    return None


def extract_target_from_message(
    message: discord.Message | None,
) -> tuple[int | None, int | None]:
    """Return ``(target_user_id, message_id)`` extracted from ``message``."""

    target_id: int | None = None
    message_id: int | None = None

    if message is None:
        return target_id, message_id

    raw_message_id = getattr(message, "id", None)
    if raw_message_id is not None:
        try:
            message_id = int(raw_message_id)
        except (TypeError, ValueError):
            message_id = None

    for user in getattr(message, "mentions", []) or []:
        if getattr(user, "bot", False):
            continue
        user_id = getattr(user, "id", None)
        if user_id is None:
            continue
        try:
            target_id = int(user_id)
        except (TypeError, ValueError):
            continue
        break

    return target_id, message_id


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
        self._panel_messages: Dict[int, int] = {}
        self._prefetched_panels: Dict[int, discord.Message] = {}
        self._initiators: Dict[int, discord.abc.User | discord.Member | None] = {}
        self._target_users: Dict[int, int | None] = {}
        self._target_message_ids: Dict[int, int | None] = {}

    def _thread_for(self, thread_id: int) -> discord.Thread | None:
        return self._threads.get(thread_id)

    def diag_target_user_id(self, thread_id: int) -> int | None:
        """Return the cached target recruit identifier for diagnostics."""

        return self._target_users.get(thread_id)

    def _log_fields(
        self,
        thread_id: int,
        *,
        actor: discord.abc.User | discord.Member | None | object = ...,
    ) -> dict[str, Any]:
        thread = self._thread_for(thread_id)
        context = logs.thread_context(thread)
        context["flow"] = self.flow
        resolved_actor: discord.abc.User | discord.Member | None
        if actor is ...:
            resolved_actor = self._initiators.get(thread_id)
        else:
            resolved_actor = cast(discord.abc.User | discord.Member | None, actor)
        context["actor"] = logs.format_actor(resolved_actor)
        handle = logs.format_actor_handle(resolved_actor)
        if handle:
            context["actor_name"] = handle
        return context

    async def _send_panel_with_retry(
        self,
        thread: discord.Thread,
        *,
        content: str,
        view: discord.ui.View,
    ) -> discord.Message:
        last_error: Exception | None = None
        for delay in (0.0, *_PANEL_RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                message = await thread.send(content, view=view)
                if getattr(message, "pinned", False):
                    try:
                        await message.unpin()
                    except Exception:
                        log.warning("failed to unpin welcome panel", exc_info=True)
                return message
            except Exception as exc:  # pragma: no cover - network
                last_error = exc
        assert last_error is not None  # for mypy
        await logs.send_welcome_exception(
            "error",
            last_error,
            **self._log_fields(int(thread.id), result="panel_failed"),
        )
        raise last_error

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
        self._initiators[thread_id] = initiator
        panels.bind_controller(thread_id, self)

        allowed_ids: set[int] = set()
        self._allowed_users[thread_id] = allowed_ids

        await self._ensure_target_cached(thread_id)
        target_id = self._target_users.get(thread_id)
        if target_id is not None:
            allowed_ids.add(int(target_id))

        await self._start_modal_step(thread, session)

    async def _start_modal_step(
        self,
        thread: discord.Thread,
        session: SessionData,
        *,
        anchor: discord.Message | None = None,
    ) -> None:
        thread_id = int(thread.id)
        if anchor is None:
            anchor = self._prefetched_panels.pop(thread_id, None)
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
        view = panels.OpenQuestionsPanelView(controller=self, thread_id=thread_id)
        message_id = self._panel_messages.get(thread_id)
        message: discord.Message | None = None
        if anchor is not None:
            message = anchor
            anchor_id = getattr(anchor, "id", None)
            if anchor_id is not None:
                try:
                    self._panel_messages[thread_id] = int(anchor_id)
                except (TypeError, ValueError):
                    pass

        parent_channel = getattr(thread, "parent", None)
        try:
            parent_id_int = int(parent_channel.id) if parent_channel is not None else None
        except (TypeError, ValueError, AttributeError):
            parent_id_int = None

        base_log = self._log_fields(thread_id)
        base_log.update(
            {
                "view": "panel",
                "view_tag": panels.WELCOME_PANEL_TAG,
                "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "diag": base_log.get("diag") or f"{self.flow}_flow",
                "flow": self.flow,
                "thread_id": thread_id,
            }
        )
        if parent_id_int is not None:
            base_log.setdefault("parent_id", parent_id_int)
            base_log.setdefault("parent_channel_id", parent_id_int)

        posted_new_message = False

        if message is None and message_id:
            try:
                message = await thread.fetch_message(message_id)
            except discord.NotFound as exc:
                error_text = f"{exc.__class__.__name__}: {exc}"
                try:
                    stale_message_id = int(message_id)
                except (TypeError, ValueError):
                    stale_message_id = None
                stale_context = dict(base_log)
                stale_context.update(
                    {
                        "event": "stale_panel",
                        "result": "stale_panel",
                        "message_id": stale_message_id,
                        "error": error_text,
                        "details": "view=panel; source=emoji",
                    }
                )
                await logs.send_welcome_log("warn", **stale_context)

                try:
                    message = await self._send_panel_with_retry(thread, content=intro, view=view)
                except Exception:
                    return
                posted_new_message = True
                message_id = int(message.id)
                self._panel_messages[thread_id] = message_id
            except Exception as exc:
                error_context = dict(base_log)
                try:
                    error_context.setdefault("message_id", int(message_id))
                except (TypeError, ValueError):
                    pass
                error_context.update(
                    {
                        "event": "stale_panel",
                        "result": "stale_panel",
                    }
                )
                await logs.send_welcome_exception("warn", exc, **error_context)

        if message is None:
            try:
                message = await self._send_panel_with_retry(thread, content=intro, view=view)
            except Exception:
                return
            posted_new_message = True
            self._panel_messages[thread_id] = message.id
            message_id = int(message.id)
        else:
            message_id = int(getattr(message, "id", message_id))
            if not posted_new_message:
                await message.edit(content=intro, view=view)
                if getattr(message, "pinned", False):
                    try:
                        await message.unpin()
                    except Exception:
                        log.warning("failed to unpin welcome panel", exc_info=True)

        panels.register_panel_message(thread_id, message.id)

        panel_log_context = dict(base_log)
        panel_log_context.update(
            {
                "event": "panel_posted",
                "result": "posted" if posted_new_message else "refreshed",
                "source": self._sources.get(thread_id),
                "message_id": int(message.id),
                "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "view_timeout": view.timeout,
                "disable_on_timeout": getattr(view, "disable_on_timeout", None),
            }
        )
        await logs.send_welcome_log(
            "info" if posted_new_message else "debug",
            **panel_log_context,
        )
        if diag.is_enabled():
            parent_id = getattr(thread, "parent_id", None)
            try:
                parent_id_int = int(parent_id) if parent_id is not None else None
            except (TypeError, ValueError):
                parent_id_int = None
            target_user_id = self._target_users.get(thread_id)
            await diag.log_event(
                "info",
                "panel_posted",
                message_id=int(message.id),
                thread_id=thread_id,
                parent_id=parent_id_int,
                schema_id=session.schema_hash,
                custom_id=panels.OPEN_QUESTIONS_CUSTOM_ID,
                view_timeout=view.timeout,
                disable_on_timeout=getattr(view, "disable_on_timeout", None),
                target_user_id=target_user_id,
                ambiguous_target=target_user_id is None,
            )

    async def _start_select_step(self, thread: discord.Thread, session: SessionData) -> None:
        thread_id = int(thread.id)
        async def gate(interaction: discord.Interaction) -> bool:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            return allowed

        pending = session.pending_step or {}
        page = int(pending.get("page", 0))
        view = build_select_view(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            interaction_check=gate,
            page=page,
        )
        if view is None:
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        view.on_page_change = self._select_page_updated(thread_id)
        store.set_pending_step(thread_id, {"kind": "select", "index": 0, "page": view.page})
        content = self._select_intro_text()
        message = self._select_messages.get(thread_id)
        if message:
            await message.edit(content=content, view=view)
        else:
            message = await thread.send(content, view=view)
            self._select_messages[thread_id] = message
        await logs.send_welcome_log(
            "debug",
            view="select",
            result="ready",
            **self._log_fields(thread_id),
        )

    def _select_changed(self, thread_id: int) -> Callable[[discord.Interaction, Question, list[str]], Awaitable[None]]:
        async def handler(
            interaction: discord.Interaction,
            question: Question,
            values: list[str],
        ) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            await self._handle_select_change(thread_id, interaction, question, values)

        return handler

    def _select_completed(self, thread_id: int) -> Callable[[discord.Interaction], Awaitable[None]]:
        async def handler(interaction: discord.Interaction) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            await self._handle_select_complete(thread_id, interaction)

        return handler

    async def _handle_modal_launch(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await self._restart_from_interaction(thread_id, interaction, context=context)
            return

        diag_state = diag.interaction_state(interaction)
        diag_state["thread_id"] = thread_id
        target_user_id = self._target_users.get(thread_id)
        diag_state["target_user_id"] = target_user_id
        diag_state["ambiguous_target"] = target_user_id is None
        diag_state["custom_id"] = panels.OPEN_QUESTIONS_CUSTOM_ID

        diag_enabled = diag.is_enabled()
        if diag_state.get("response_is_done"):
            if diag_enabled:
                await diag.log_event(
                    "info",
                    "modal_launch_skipped",
                    skip_reason="response_done",
                    **diag_state,
                )
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

        questions_for_step = list(modals[index].questions)
        modal = WelcomeQuestionnaireModal(
            questions=questions_for_step,
            step_index=index,
            total_steps=len(modals),
            title_prefix=self._modal_title_prefix(),
            answers=session.answers,
            visibility=session.visibility,
            on_submit=self._modal_submitted(thread_id, questions_for_step, index),
        )
        store.set_pending_step(thread_id, {"kind": "modal", "index": index})
        diag_state["modal_index"] = index
        diag_state["schema_id"] = session.schema_hash
        diag_state["about_to_send_modal"] = True
        diag_tasks: list[Awaitable[None]] = []
        if diag_enabled:
            diag_tasks.append(diag.log_event("info", "modal_launch_pre", **diag_state))
            if diag_state.get("response_is_done"):
                diag_tasks.append(
                    diag.log_event(
                        "info",
                        "modal_launch_followup",
                        followup_path=True,
                        **diag_state,
                    )
                )
        display_name = _display_name(getattr(interaction, "user", None))
        channel_obj: discord.abc.GuildChannel | discord.Thread | None
        channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else thread
        channel_label = _channel_path(channel_obj)
        log.info(
            "✅ Welcome — modal_open • user=%s • channel=%s",
            display_name,
            channel_label,
        )
        try:
            await interaction.response.send_modal(modal)
        except discord.InteractionResponded:
            log.warning(
                "⚠️ Welcome — modal_already_responded • user=%s • channel=%s",
                display_name,
                channel_label,
            )
            if diag_enabled:
                diag_tasks.append(
                    diag.log_event(
                        "warning",
                        "modal_launch_skipped",
                        skip_reason="interaction_already_responded",
                        **diag_state,
                    )
                )
                await asyncio.gather(*diag_tasks, return_exceptions=True)
            return
        except Exception as exc:
            if diag_enabled:
                diag_tasks.append(
                    diag.log_event(
                        "error",
                        "modal_launch_error",
                        exception_type=exc.__class__.__name__,
                        exception_message=str(exc),
                        **diag_state,
                    )
                )
                await asyncio.gather(*diag_tasks, return_exceptions=True)
            raise
        else:
            if diag_enabled:
                diag_tasks.append(
                    diag.log_event("info", "modal_launch_sent", modal_sent=True, **diag_state)
                )
                await asyncio.gather(*diag_tasks, return_exceptions=True)
        await logs.send_welcome_log(
            "debug",
            view="modal",
            result="launched",
            index=index,
            **self._log_fields(thread_id, actor=interaction.user),
        )

    async def _restart_from_interaction(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        channel = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        thread = self._threads.get(thread_id) or channel
        message = getattr(interaction, "message", None)
        message_id = getattr(message, "id", None)

        log_payload = self._log_fields(thread_id, actor=interaction.user)
        if context is not None:
            log_payload.update(context)
        if thread is not None:
            log_payload.setdefault("thread", logs.format_thread(getattr(thread, "id", None)))
            parent_id = getattr(thread, "parent_id", None)
            if parent_id is not None:
                try:
                    log_payload.setdefault("parent_channel_id", int(parent_id))
                except (TypeError, ValueError):
                    pass
        if message_id is not None:
            try:
                log_payload.setdefault("message_id", int(message_id))
            except (TypeError, ValueError):
                pass
        log_payload["view"] = "panel"
        log_payload.setdefault("view_tag", panels.WELCOME_PANEL_TAG)
        log_payload.setdefault("custom_id", panels.OPEN_QUESTIONS_CUSTOM_ID)
        log_payload["result"] = "restarted"

        await _safe_ephemeral(interaction, "♻️ Restarting the onboarding form…")

        await logs.send_welcome_log("info", **log_payload)

        self._cleanup_session(thread_id)

        if thread is None:
            failure = dict(log_payload)
            failure["result"] = "error"
            failure["reason"] = "thread_missing"
            await logs.send_welcome_log("error", **failure)
            return

        try:
            from modules.onboarding.welcome_flow import start_welcome_dialog

            panel_message = message if isinstance(message, discord.Message) else None
            panel_id = None
            if message_id is not None:
                try:
                    panel_id = int(message_id)
                except (TypeError, ValueError):
                    panel_id = None
            await start_welcome_dialog(
                thread,
                interaction.user,
                "panel_restart",
                bot=self.bot,
                panel_message_id=panel_id,
                panel_message=panel_message,
            )
        except Exception as exc:  # pragma: no cover - network restart errors
            error_payload = dict(log_payload)
            error_payload["result"] = "error"
            await logs.send_welcome_exception("error", exc, **error_payload)

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
        await interaction.response.defer(ephemeral=True)

        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="modal",
                result="inactive",
                index=index,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session is no longer active.")
            return

        gate_context: dict[str, Any] = {
            "view": "modal",
            "view_tag": panels.WELCOME_PANEL_TAG,
            "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
            "view_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
            "step_index": index,
            "flow": self.flow,
        }
        gate_context.setdefault("diag", f"{self.flow}_flow")
        schema_id = getattr(session, "schema_hash", None)
        if schema_id is not None:
            try:
                gate_context["schema_id"] = int(schema_id)
            except (TypeError, ValueError):
                gate_context["schema_id"] = schema_id

        allowed, _ = await self.check_interaction(
            thread_id,
            interaction,
            context=gate_context,
        )
        if not allowed:
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
        await logs.send_welcome_log(
            "debug",
            view="modal",
            result="saved",
            index=index,
            **self._log_fields(thread_id, actor=interaction.user),
        )

        display_name = _display_name(getattr(interaction, "user", None))
        channel_obj: discord.abc.GuildChannel | discord.Thread | None
        channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else thread
        log.info(
            "✅ Welcome — modal_submit_ok • user=%s • channel=%s",
            display_name,
            _channel_path(channel_obj),
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
            await logs.send_welcome_log(
                "warn",
                view="select",
                result="inactive",
                question=question.qid,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        self._store_select_answer(session, question, values)
        session.visibility = rules.evaluate_visibility(
            self._questions[thread_id],
            session.answers,
        )
        store.set_pending_step(thread_id, session.pending_step)

        async def gate(interaction: discord.Interaction) -> bool:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            return allowed

        pending = session.pending_step or {}
        page = int(pending.get("page", 0))
        view = build_select_view(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            interaction_check=gate,
            page=page,
        )
        if view is None:
            store.set_pending_step(thread_id, None)
            await interaction.response.edit_message(view=None)
            await logs.send_welcome_log(
                "debug",
                view="select",
                result="completed",
                question=question.qid,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        view.on_page_change = self._select_page_updated(thread_id)
        store.set_pending_step(thread_id, {"kind": "select", "index": 0, "page": view.page})
        await interaction.response.edit_message(view=view)
        await logs.send_welcome_log(
            "debug",
            view="select",
            result="changed",
            question=question.qid,
            **self._log_fields(thread_id, actor=interaction.user),
        )

    async def _handle_select_complete(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="select",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
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
        await logs.send_welcome_log(
            "info",
            view="select",
            result="submitted",
            **self._log_fields(thread_id, actor=interaction.user),
        )
        await self._show_preview(thread, session)

    def _select_page_updated(self, thread_id: int) -> Callable[[discord.Interaction, int], Awaitable[None]]:
        async def handler(interaction: discord.Interaction, page: int) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            session = store.get(thread_id)
            if session is None:
                return
            pending = dict(session.pending_step or {"kind": "select", "index": 0})
            pending["page"] = page
            store.set_pending_step(thread_id, pending)

        return handler

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
            await logs.send_welcome_log(
                "debug",
                view="preview",
                result="rendered",
                source=self._sources.get(thread_id, "unknown"),
                schema=session.schema_hash,
                **self._log_fields(thread_id),
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
            await logs.send_welcome_log(
                "warn",
                view="preview",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        await interaction.response.edit_message(view=None)

        preview_message = self._preview_messages.pop(thread_id, None)
        if preview_message is not None:
            try:
                await preview_message.delete()
            except Exception:
                try:
                    await preview_message.edit(view=None)
                except Exception:
                    log.warning("failed to remove preview after confirmation", exc_info=True)

        summary_author = self._resolve_summary_author(thread, interaction)
        summary_embed = build_summary_embed(
            self.flow,
            session.answers,
            summary_author,
            session.schema_hash or "",
            session.visibility,
        )

        await thread.send(embed=summary_embed)
        await thread.send("@RecruitmentCoordinator")

        await logs.send_welcome_log(
            "info",
            result="completed",
            view="preview",
            source=self._sources.get(thread_id, "unknown"),
            schema=session.schema_hash,
            details=_final_fields(self._questions[thread_id], session.answers),
            **self._log_fields(thread_id, actor=interaction.user),
        )

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
            await logs.send_welcome_log(
                "warn",
                view="preview",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        await interaction.response.edit_message(view=None)
        await _safe_followup(
            interaction,
            "🛠️ Re-opening the form so you can make changes.",
        )
        await logs.send_welcome_log(
            "info",
            view="preview",
            result="reopened",
            **self._log_fields(thread_id, actor=interaction.user),
        )
        anchor = getattr(interaction, "message", None)
        await self._start_modal_step(thread, session, anchor=anchor)

    def _cleanup_session(self, thread_id: int) -> None:
        store.end(thread_id)
        self._threads.pop(thread_id, None)
        self._questions.pop(thread_id, None)
        self._select_messages.pop(thread_id, None)
        self._preview_messages.pop(thread_id, None)
        self._sources.pop(thread_id, None)
        self._allowed_users.pop(thread_id, None)
        self._target_users.pop(thread_id, None)
        self._target_message_ids.pop(thread_id, None)
        self._preview_logged.discard(thread_id)
        panel_message_id = self._panel_messages.pop(thread_id, None)
        if panel_message_id is not None:
            panels.mark_panel_inactive_by_message(panel_message_id)
        self._prefetched_panels.pop(thread_id, None)
        panels.unbind_controller(thread_id)

    async def _ensure_target_cached(
        self, thread_id: int, *, refresh_if_none: bool = False
    ) -> None:
        cached = self._target_users.get(thread_id, ...)
        if cached is not ...:
            if not (cached is None and refresh_if_none):
                return

        thread = self._threads.get(thread_id)
        if thread is None:
            self._target_users[thread_id] = None
            return

        target_id: int | None = None
        message_id: int | None = None

        message = await locate_welcome_message(thread)
        target_id, message_id = extract_target_from_message(message)

        self._target_users[thread_id] = target_id
        if message_id is not None:
            self._target_message_ids[thread_id] = message_id

    @staticmethod
    def _member_role_ids(member: discord.abc.User | discord.Member | None) -> set[int]:
        if not isinstance(member, discord.Member):
            return set()
        role_ids: set[int] = set()
        for role in getattr(member, "roles", []) or []:
            role_id = getattr(role, "id", None)
            if role_id is None:
                continue
            try:
                role_ids.add(int(role_id))
            except (TypeError, ValueError):
                continue
        return role_ids

    async def _log_access(
        self,
        level: str,
        result: str,
        thread_id: int,
        interaction: discord.Interaction,
        context: dict[str, Any],
        **extra: Any,
    ) -> None:
        payload = self._log_fields(thread_id, actor=interaction.user)
        payload.update(context)
        payload["result"] = result
        if extra:
            payload.update(extra)
        await logs.send_welcome_log(level, **payload)

    async def check_interaction(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        allowed_cache = self._allowed_users.setdefault(thread_id, set())
        actor = interaction.user
        actor_id = getattr(actor, "id", None)

        log_context: dict[str, Any] | None = None
        if context is not None:
            log_context = dict(context)
            if actor_id is not None:
                log_context.setdefault("actor_id", int(actor_id))
            target_message_id = self._target_message_ids.get(thread_id)
            if target_message_id is not None:
                log_context.setdefault("target_message_id", int(target_message_id))
            thread = self._thread_for(thread_id)
            parent_id = getattr(thread, "parent_id", None)
            if parent_id is not None:
                log_context.setdefault("parent_channel_id", int(parent_id))
        target_id = self._target_users.get(thread_id)
        if target_id is not None and log_context is not None:
            log_context.setdefault("target_user_id", int(target_id))

        if actor_id is not None and actor_id in allowed_cache:
            fallback_thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else self._thread_for(thread_id)
            _log_gate(interaction, allowed=True, reason="cached", fallback_thread=fallback_thread)
            if log_context is not None:
                await self._log_access("info", "allowed", thread_id, interaction, log_context)
            return True, None

        thread = self._thread_for(thread_id)
        subject = interaction.channel if isinstance(interaction.channel, discord.Thread) else None

        if subject is None:
            _log_gate(interaction, allowed=False, reason="no_thread", fallback_thread=thread)
            if log_context is not None:
                await self._log_access("warn", "denied_scope", thread_id, interaction, log_context)
            await _safe_ephemeral(
                interaction,
                "⚠️ This onboarding panel only works inside ticket threads.",
            )
            return False, "no_thread"

        perms = subject.permissions_for(cast(discord.abc.Snowflake, actor))
        if not perms.view_channel:
            _log_gate(interaction, allowed=False, reason="no_view_channel", fallback_thread=subject)
            if log_context is not None:
                await self._log_access(
                    "warn",
                    "denied_permission",
                    thread_id,
                    interaction,
                    log_context,
                    reason="no_view_channel",
                )
            await _safe_ephemeral(
                interaction,
                "⚠️ You need view access to this thread before starting the onboarding form.",
            )
            return False, "no_view_channel"

        if actor_id is not None:
            allowed_cache.add(int(actor_id))
        if log_context is not None:
            await self._log_access("info", "allowed", thread_id, interaction, log_context)
        _log_gate(interaction, allowed=True, reason="view_channel", fallback_thread=subject)
        return True, None

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

    def _resolve_summary_author(
        self, thread: discord.Thread, interaction: discord.Interaction
    ) -> discord.Member:
        owner = getattr(thread, "owner", None)
        if isinstance(owner, discord.Member):
            return owner

        guild = thread.guild
        owner_id = getattr(thread, "owner_id", None)
        if guild and owner_id:
            member = guild.get_member(owner_id)
            if member is not None:
                return member

        user = interaction.user
        if isinstance(user, discord.Member):
            return user

        if guild is not None and getattr(user, "id", None):
            member = guild.get_member(int(user.id))
            if member is not None:
                return member

        if guild is not None:
            me = guild.me
            if me is not None:
                return me

        user_obj = interaction.user
        if isinstance(user_obj, discord.User):
            return cast(discord.Member, user_obj)

        raise TypeError("Unable to resolve summary author for onboarding thread")


class WelcomeController(BaseWelcomeController):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot, flow="welcome")


class _PreviewView(discord.ui.View):
    def __init__(self, controller: BaseWelcomeController, thread_id: int) -> None:
        super().__init__(timeout=600)
        self.controller = controller
        self.thread_id = thread_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - network
        allowed, _ = await self.controller.check_interaction(self.thread_id, interaction)
        return allowed

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="ob.confirm")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        if getattr(interaction, "_c1c_claimed", False):
            return
        setattr(interaction, "_c1c_claimed", True)
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        context = {
            **logs.thread_context(thread if isinstance(thread, discord.Thread) else None),
            "actor": logs.format_actor(interaction.user),
            "view": "preview",
            "view_id": "ob.confirm",
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            context["actor_name"] = actor_name
        await logs.send_welcome_log("debug", result="clicked", **context)
        await self.controller._handle_confirm(self.thread_id, interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, custom_id="ob.edit")
    async def edit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        if getattr(interaction, "_c1c_claimed", False):
            return
        setattr(interaction, "_c1c_claimed", True)
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        context = {
            **logs.thread_context(thread if isinstance(thread, discord.Thread) else None),
            "actor": logs.format_actor(interaction.user),
            "view": "preview",
            "view_id": "ob.edit",
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            context["actor_name"] = actor_name
        await logs.send_welcome_log("debug", result="clicked", **context)
        await self.controller._handle_edit(self.thread_id, interaction)

    async def on_timeout(self) -> None:  # pragma: no cover - network
        for child in self.children:
            child.disabled = True


async def _safe_ephemeral(interaction: discord.Interaction, message: str) -> None:
    diag_state = diag.interaction_state(interaction)
    response_done = False
    try:
        response_done = bool(interaction.response.is_done())
    except Exception:  # pragma: no cover - defensive guard
        response_done = False
    deny_path = "followup" if response_done else "initial_response"
    diag_state["deny_path"] = deny_path
    diag_state["response_is_done"] = response_done
    if diag.is_enabled():
        await diag.log_event("info", "deny_notice_pre", **diag_state)
    try:
        if response_done:
            await _edit_deferred_response(interaction, message)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        if diag.is_enabled():
            await diag.log_event("info", "deny_notice_sent", **diag_state)
    except Exception:  # pragma: no cover - defensive network handling
        if diag.is_enabled():
            error_type = None
            status = None
            code = None
            if isinstance(exc := sys.exc_info()[1], discord.Forbidden):
                error_type = "Forbidden"
                status = getattr(exc, "status", None)
                code = getattr(exc, "code", None)
            elif isinstance(exc, discord.HTTPException):
                error_type = "HTTPException"
                status = getattr(exc, "status", None)
                code = getattr(exc, "code", None)
            else:
                error_type = exc.__class__.__name__ if exc else None
            await diag.log_event(
                "error",
                "deny_notice_error",
                error_type=error_type,
                status=status,
                code=code,
                **diag_state,
            )
        log.warning("failed to send denial response", exc_info=True)


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
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            log.warning("failed to send follow-up", exc_info=True)

    return runner()


__all__ = ["WelcomeController", "BaseWelcomeController"]
