"""Persistent UI components for the onboarding welcome panel."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, Optional, Sequence

import discord

from c1c_coreops import rbac  # Retained for compatibility with existing tests/hooks.
from modules.onboarding import diag, logs
from .wizard import OnboardWizard

__all__ = [
    "OPEN_QUESTIONS_CUSTOM_ID",
    "WELCOME_PANEL_TAG",
    "OnboardWizard",
    "OpenQuestionsPanelView",
    "bind_controller",
    "get_controller",
    "get_panel_message_id",
    "is_panel_live",
    "mark_panel_inactive_by_message",
    "register_panel_message",
    "register_persistent_views",
    "unbind_controller",
]

log = logging.getLogger("c1c.onboarding.ui.panels")

OPEN_QUESTIONS_CUSTOM_ID = "welcome.panel.open"
WELCOME_PANEL_TAG = "welcome_panel"


class _ControllerProtocol:
    async def check_interaction(
        self, thread_id: int, interaction: discord.Interaction, *, context: dict[str, Any] | None = None
    ) -> tuple[bool, str | None]:  # pragma: no cover - protocol
        ...

    async def _handle_modal_launch(self, thread_id: int, interaction: discord.Interaction) -> None:  # pragma: no cover - protocol
        ...

    def render_step(self, thread_id: int | None, step: int) -> str:  # pragma: no cover - protocol
        ...

    async def capture_step(self, interaction: discord.Interaction, thread_id: int | None, step: int) -> None:  # pragma: no cover - protocol
        ...

    def is_finished(self, thread_id: int | None, step: int) -> bool:  # pragma: no cover - protocol
        ...

    async def finish_and_summarize(self, interaction: discord.Interaction, thread_id: int | None) -> None:  # pragma: no cover - protocol
        ...


_CONTROLLERS: Dict[int, _ControllerProtocol] = {}
_PANEL_MESSAGES: Dict[int, int] = {}
_ACTIVE_PANEL_MESSAGE_IDS: set[int] = set()
_REGISTRATION_COUNTS: Dict[str, int] = {}


def _display_name(user: discord.abc.User | discord.Member | None) -> str:
    if user is None:
        return "<unknown>"
    return getattr(user, "display_name", None) or getattr(user, "global_name", None) or getattr(user, "name", None) or "<unknown>"


def _channel_path(channel: discord.abc.GuildChannel | discord.Thread | None) -> str:
    if isinstance(channel, discord.Thread):
        parent = getattr(channel, "parent", None)
        parent_label = f"#{getattr(parent, 'name', 'unknown')}" if parent else "#unknown"
        return f"{parent_label} › {getattr(channel, 'name', 'thread')}"
    if isinstance(channel, discord.abc.GuildChannel):
        return f"#{getattr(channel, 'name', 'channel')}"
    return "#unknown"


def _log_followup_fallback(
    interaction: discord.Interaction,
    *,
    action: str,
    error: Exception,
) -> None:
    user_name = _display_name(getattr(interaction, "user", None))
    channel = _channel_path(getattr(interaction, "channel", None))
    why = getattr(error, "__class__", type(error)).__name__
    message = f"⚠️ Welcome — followup fallback • action={action} • user={user_name} • channel={channel} • why={why}"
    log.warning(message)


async def _edit_original_response(
    interaction: discord.Interaction,
    *,
    content: str,
) -> None:
    try:
        await interaction.edit_original_response(content=content)
    except Exception as exc:  # pragma: no cover - defensive fallback
        _log_followup_fallback(interaction, action="edit_original", error=exc)
        followup = getattr(interaction, "followup", None)
        if followup is None:
            log.debug("followup handler missing; skipping deferred notice")
            return
        try:
            await followup.send(content, ephemeral=True)
        except Exception:  # pragma: no cover - final guard
            log.warning("failed to send followup notice", exc_info=True)


async def _defer_interaction(interaction: discord.Interaction) -> None:
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.Forbidden:
        await interaction.response.defer()
    except discord.InteractionResponded:
        return


def _restart_context_from_state(
    interaction: discord.Interaction,
    state: dict[str, Any],
) -> dict[str, Any]:
    context = {"view": "panel", "view_tag": WELCOME_PANEL_TAG, "custom_id": "welcome.panel.restart"}
    channel = getattr(interaction, "channel", None)
    thread = channel if isinstance(channel, discord.Thread) else None
    context.update(logs.thread_context(thread))
    message = getattr(interaction, "message", None)
    if message is not None:
        message_id = getattr(message, "id", None)
        if message_id is not None:
            try:
                context["message_id"] = int(message_id)
            except (TypeError, ValueError):
                context["message_id"] = message_id
    actor_name = logs.format_actor_handle(getattr(interaction, "user", None))
    if actor_name:
        context["actor_name"] = actor_name
    context["state_view"] = state.get("view")
    return context


def _claim_interaction(interaction: discord.Interaction) -> bool:
    """Mark this interaction as claimed by the welcome panel handler."""

    # NOTE: discord.Interaction does not expose ``_c1c_claimed`` by default.
    # Always guard with ``getattr`` before first use.
    if getattr(interaction, "_c1c_claimed", False):
        return False
    try:
        setattr(interaction, "_c1c_claimed", True)
    except Exception:
        # As a last resort, allow the flow to continue even if we cannot mark
        # the ad-hoc attribute.
        return True
    return True


def bind_controller(thread_id: int, controller: _ControllerProtocol) -> None:
    _CONTROLLERS[thread_id] = controller


def unbind_controller(thread_id: int) -> None:
    _CONTROLLERS.pop(thread_id, None)
    message_id = _PANEL_MESSAGES.pop(thread_id, None)
    if message_id is not None:
        _ACTIVE_PANEL_MESSAGE_IDS.discard(message_id)


def get_controller(thread_id: int | None) -> _ControllerProtocol | None:
    if thread_id is None:
        return None
    return _CONTROLLERS.get(thread_id)


def register_panel_message(thread_id: int, message_id: int) -> None:
    _PANEL_MESSAGES[thread_id] = message_id
    _ACTIVE_PANEL_MESSAGE_IDS.add(message_id)


def get_panel_message_id(thread_id: int) -> Optional[int]:
    return _PANEL_MESSAGES.get(thread_id)


def is_panel_live(message_id: int | None) -> bool:
    if message_id is None:
        return False
    return message_id in _ACTIVE_PANEL_MESSAGE_IDS


def mark_panel_inactive_by_message(message_id: int | None) -> None:
    if message_id is None:
        return
    _ACTIVE_PANEL_MESSAGE_IDS.discard(message_id)
    to_delete = [thread_id for thread_id, mid in _PANEL_MESSAGES.items() if mid == message_id]
    for thread_id in to_delete:
        _PANEL_MESSAGES.pop(thread_id, None)


def register_persistent_views(bot: discord.Client) -> None:
    view = OpenQuestionsPanelView()
    registered = False
    duplicate = False
    stacksite: str | None = None
    try:
        bot.add_view(view)
        registered = True
    except Exception:  # pragma: no cover - defensive logging
        log.warning("failed to register persistent welcome panel view", exc_info=True)
    finally:
        if diag.is_enabled():
            key = view.__class__.__name__
            _REGISTRATION_COUNTS[key] = _REGISTRATION_COUNTS.get(key, 0) + 1
            duplicate = _REGISTRATION_COUNTS[key] > 1
            if duplicate:
                stacksite = diag.relative_stack_site(frame_level=2)
            custom_ids = [
                child.custom_id
                for child in view.children
                if isinstance(child, discord.ui.Button) and child.custom_id
            ]
            fields = {
                "view": key,
                "registered": registered,
                "timeout": view.timeout,
                "disable_on_timeout": getattr(view, "disable_on_timeout", None),
                "custom_ids": custom_ids,
            }
            if duplicate:
                fields["duplicate_registration"] = True
                if stacksite:
                    fields["stacksite"] = stacksite
            diag.log_event_sync("info", "persistent_view_registered", **fields)
    if registered:
        log.info("🧭 welcome.view registered (timeout=%s)", view.timeout)
        log.info("✅ Welcome — persistent-view • view=%s", view.__class__.__name__)


class OpenQuestionsPanelView(discord.ui.View):
    """Persistent panel view that launches the welcome modal flow."""

    CUSTOM_ID = OPEN_QUESTIONS_CUSTOM_ID
    ERROR_NOTICE = (
        "Couldn\u2019t open the questions just now. A recruiter has been pinged. Please try again in a moment."
    )

    def __init__(
        self,
        *,
        controller: _ControllerProtocol | None = None,
        thread_id: int | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self._controller = controller
        self._thread_id = thread_id
        self.disable_on_timeout = False
        self._error_notice_ids: set[int] = set()
        if diag.is_enabled():
            diag.log_event_sync(
                "debug",
                "panel_view_initialized",
                view=self.__class__.__name__,
                timeout=self.timeout,
                disable_on_timeout=self.disable_on_timeout,
                thread_id=int(thread_id) if thread_id is not None else None,
            )

    def _resolve(self, interaction: discord.Interaction) -> tuple[_ControllerProtocol | None, int | None]:
        thread_id = self._thread_id or getattr(interaction.channel, "id", None) or interaction.channel_id
        controller = self._controller or _CONTROLLERS.get(int(thread_id) if thread_id is not None else None)
        if controller is None and thread_id is not None:
            controller = _CONTROLLERS.get(int(thread_id))
        return controller, int(thread_id) if thread_id is not None else None

    def as_disabled(self, *, label: str | None = None) -> "OpenQuestionsPanelView":
        """Return a disabled clone of this view for optimistic locking."""

        clone = self.__class__(controller=self._controller, thread_id=self._thread_id)
        for child in clone.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                if label and getattr(child, "custom_id", None) == OPEN_QUESTIONS_CUSTOM_ID:
                    child.label = label
        return clone

    @classmethod
    async def refresh_enabled(
        cls,
        interaction: discord.Interaction | None,
        *,
        controller: _ControllerProtocol | None,
        thread_id: int | None,
    ) -> None:
        if interaction is None:
            return
        view = cls(controller=controller, thread_id=thread_id)
        response = getattr(interaction, "response", None)
        if response is not None:
            is_done = getattr(response, "is_done", None)
            responded = False
            if callable(is_done):
                try:
                    responded = bool(is_done())
                except Exception:
                    responded = False
            elif isinstance(is_done, bool):
                responded = is_done
            if not responded:
                try:
                    await response.edit_message(view=view)
                    return
                except Exception:
                    log.debug("failed to refresh panel via interaction response", exc_info=True)
        message = getattr(interaction, "message", None)
        if isinstance(message, discord.Message):
            try:
                await message.edit(view=view)
            except Exception:
                log.warning("failed to refresh panel message", exc_info=True)

    async def _restore_enabled(self, interaction: discord.Interaction) -> None:
        await self.__class__.refresh_enabled(
            interaction,
            controller=self._controller,
            thread_id=self._thread_id,
        )

    @discord.ui.button(
        label="Open questions",
        style=discord.ButtonStyle.primary,
        custom_id=OPEN_QUESTIONS_CUSTOM_ID,
    )
    async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Stage 1: post a clean launcher so the modal opens on a fresh interaction."""

        controller, thread_id = self._resolve(interaction)
        if controller is None or thread_id is None:
            await self._restart_from_view(interaction, log_context="launch_resolve_failed")
            return

        diag_state = diag.interaction_state(interaction)
        diag_state["thread_id"] = thread_id
        diag_state["custom_id"] = OPEN_QUESTIONS_CUSTOM_ID

        channel = getattr(interaction, "channel", None)
        if not isinstance(channel, discord.Thread):
            await self._ensure_error_notice(interaction)
            return

        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        view = OnboardWizard(controller=controller, thread_id=thread_id, step=0)
        content = controller.render_step(thread_id, step=0)

        try:
            await channel.send(content, view=view)
        except Exception:
            await self._ensure_error_notice(interaction)
            raise

        if diag.is_enabled():
            await diag.log_event("info", "wizard_launch_sent", **diag_state)

    async def _post_retry_start(self, interaction: discord.Interaction, *, reason: str) -> None:
        """Post a small prompt with a retry button that uses a fresh interaction."""

        controller, thread_id = self._resolve(interaction)
        channel = getattr(interaction, "channel", None)
        if channel is None or not hasattr(channel, "send"):
            return

        if controller is None or thread_id is None:
            return

        if diag.is_enabled():
            await diag.log_event(
                "info",
                "retry_prompt_posted",
                thread_id=thread_id,
                reason=reason,
            )

        existing_retry_id = None
        retry_registry = getattr(controller, "retry_message_ids", None)
        if isinstance(retry_registry, dict):
            existing_retry_id = retry_registry.get(thread_id)

        if existing_retry_id:
            try:
                message = await channel.fetch_message(existing_retry_id)
                await message.delete()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass

        from .views import RetryStartView  # local import to avoid circular dependency

        view = RetryStartView(controller, thread_id)
        try:
            message = await channel.send(
                "Let’s capture some details. Tap **Open questions** to begin.",
                view=view,
            )
        except Exception:  # pragma: no cover - network fallback
            log.warning("failed to post retry start prompt", exc_info=True)
            return

        if isinstance(retry_registry, dict):
            retry_registry[thread_id] = getattr(message, "id", None)

    @discord.ui.button(
        label="Restart",
        style=discord.ButtonStyle.secondary,
        custom_id="welcome.panel.restart",
    )
    async def restart(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await _defer_interaction(interaction)
        try:
            await self._handle_restart(interaction)
        except Exception:
            await self._ensure_error_notice(interaction)
            raise

    async def _handle_launch(
        self, interaction: discord.Interaction, *, response_was_done: bool = False
    ) -> None:
        controller, thread_id = self._resolve(interaction)
        if controller is None or thread_id is None:
            await self._restart_from_view(
                interaction, log_context={"reason": "launch_resolve_failed"}
            )
            return

        diag_state = diag.interaction_state(interaction)
        diag_state["thread_id"] = thread_id
        diag_state["custom_id"] = OPEN_QUESTIONS_CUSTOM_ID

        if response_was_done:
            if diag.is_enabled():
                await diag.log_event(
                    "warning",
                    "modal_launch_skipped",
                    skip_reason="interaction_already_responded",
                    **diag_state,
                )
            await self._post_retry_start(interaction, reason="response_done")
            return

        # Safe path: we haven’t answered yet → disable the button then continue
        try:
            await interaction.response.edit_message(view=self.as_disabled(label="Launching…"))
        except discord.InteractionResponded:
            # If already answered by something else, still proceed
            pass

        preload_questions = getattr(controller, "get_or_load_questions", None)
        questions_cache: Any = None
        cache_dict = getattr(controller, "questions_by_thread", None)
        if isinstance(cache_dict, dict):
            questions_cache = cache_dict.get(thread_id)
        if callable(preload_questions) and not questions_cache:
            try:
                await preload_questions(thread_id)
            except Exception as exc:  # pragma: no cover - best-effort preload
                await self._restore_enabled(interaction)
                if diag.is_enabled():
                    await diag.log_event(
                        "warning",
                        "onboard_preload_failed",
                        thread_id=thread_id,
                        error=str(exc),
                    )
                log.warning("welcome question preload failed", exc_info=True)
                await self._ensure_error_notice(interaction)
                return

        questions_dict = getattr(controller, "questions_by_thread", {})
        thread_questions = questions_dict.get(thread_id) if isinstance(questions_dict, dict) else None
        if not thread_questions:
            await self._restore_enabled(interaction)
            await self._ensure_error_notice(interaction)
            return

        # Rolling-card prototype replaces the inline wizard.
        starter = getattr(controller, "start_session_from_button", None)
        if callable(starter):
            try:
                await starter(
                    thread_id,
                    actor_id=getattr(getattr(interaction, "user", None), "id", None),
                    channel=getattr(interaction, "channel", None),
                    guild=getattr(interaction, "guild", None),
                    interaction=interaction,
                )
            except Exception:
                await self._restore_enabled(interaction)
                await self._ensure_error_notice(interaction)
                raise
            return

    async def _handle_restart(self, interaction: discord.Interaction) -> None:
        state = diag.interaction_state(interaction)
        controller = self._controller
        thread_id = state.get("thread_id")
        if not _claim_interaction(interaction):
            return
        if controller is None or thread_id is None:
            await self._restart_from_view(interaction, _restart_context_from_state(interaction, state))
            return

        controller_context = {"view": "panel", "view_tag": WELCOME_PANEL_TAG, "custom_id": "welcome.panel.restart"}
        try:
            allowed, _ = await controller.check_interaction(
                thread_id,
                interaction,
                context=controller_context,
            )
            if not allowed:
                return
        except Exception:
            await self._ensure_error_notice(interaction)
            raise

        await self._restart_from_view(interaction, _restart_context_from_state(interaction, state))

    async def on_timeout(self) -> None:  # pragma: no cover - network
        if diag.is_enabled():
            disabled_components = all(getattr(child, "disabled", False) for child in self.children)
            await diag.log_event(
                "warning",
                "panel_view_timeout",
                view=self.__class__.__name__,
                timeout=self.timeout,
                disable_on_timeout=getattr(self, "disable_on_timeout", None),
                thread_id=int(self._thread_id) if self._thread_id is not None else None,
                on_timeout_called=True,
                disabled_components=disabled_components,
                edit_attempted=False,
                post_attempted=False,
            )
        await super().on_timeout()

    async def _restart_from_view(
        self,
        interaction: discord.Interaction,
        log_context: dict[str, Any],
    ) -> None:
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        message = getattr(interaction, "message", None)
        message_id = getattr(message, "id", None)

        restart_context = dict(log_context)
        restart_context["result"] = "restarted"

        await self._notify_restart(interaction)

        await logs.send_welcome_log("info", **restart_context)

        if not isinstance(thread, discord.Thread):
            failure_context = dict(restart_context)
            failure_context["result"] = "error"
            failure_context["reason"] = "thread_missing"
            await logs.send_welcome_log("error", **failure_context)
            return

        try:
            from modules.onboarding.welcome_flow import start_welcome_dialog

            panel_id = None
            if message_id is not None:
                try:
                    panel_id = int(message_id)
                except (TypeError, ValueError):
                    panel_id = None
            panel_message = message if isinstance(message, discord.Message) else None
            await start_welcome_dialog(
                thread,
                interaction.user,
                "panel_restart",
                bot=interaction.client,
                panel_message_id=panel_id,
                panel_message=panel_message,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            error_context = dict(restart_context)
            error_context["result"] = "error"
            await logs.send_welcome_exception("error", exc, **error_context)

    async def _ensure_error_notice(self, interaction: discord.Interaction) -> None:
        identifier = getattr(interaction, "id", None)
        if identifier is None:
            identifier = id(interaction)
        try:
            key = int(identifier)
        except (TypeError, ValueError):
            key = id(interaction)
        if key in self._error_notice_ids:
            return
        self._error_notice_ids.add(key)
        if interaction.response.is_done():
            await _edit_original_response(interaction, content=self.ERROR_NOTICE)
            return
        try:
            await interaction.response.send_message(self.ERROR_NOTICE, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send error notice", exc_info=True)

    async def _notify_error(self, interaction: discord.Interaction) -> None:
        await self._ensure_error_notice(interaction)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        try:
            snapshot, perms_text, _ = diag.permission_snapshot(interaction)
        except Exception:
            snapshot = None
            perms_text = None

        channel = getattr(interaction, "channel", None)
        thread = channel if isinstance(channel, discord.Thread) else None
        parent_channel = getattr(thread, "parent", None) if thread is not None else None

        extra: dict[str, Any] = {
            "custom_id": getattr(item, "custom_id", None),
            "component_type": item.__class__.__name__ if item is not None else None,
            "message_id": getattr(interaction.message, "id", None)
            if interaction.message
            else None,
            "interaction_id": getattr(interaction, "id", None),
            "actor": logs.format_actor(interaction.user),
            "actor_id": getattr(interaction.user, "id", None),
            "actor_name": logs.format_actor_handle(interaction.user),
            "app_permissions": perms_text,
            "app_perms_text": perms_text,
            "app_permissions_snapshot": snapshot,
        }

        guild = getattr(interaction, "guild", None)
        guild_id = getattr(guild, "id", None) or getattr(interaction, "guild_id", None)
        if guild_id is not None:
            try:
                extra["guild_id"] = int(guild_id)
            except (TypeError, ValueError):
                extra["guild_id"] = guild_id

        if thread is not None:
            extra.update(logs.thread_context(thread))
            thread_id = getattr(thread, "id", None)
            if thread_id is not None:
                try:
                    extra["thread_id"] = int(thread_id)
                except (TypeError, ValueError):
                    extra["thread_id"] = thread_id
            parent_id = getattr(parent_channel, "id", None)
            if parent_id is not None:
                try:
                    extra["parent_channel_id"] = int(parent_id)
                except (TypeError, ValueError):
                    extra["parent_channel_id"] = parent_id
        elif channel is not None:
            channel_id = getattr(channel, "id", None)
            if channel_id is not None:
                try:
                    extra["channel_id"] = int(channel_id)
                except (TypeError, ValueError):
                    extra["channel_id"] = channel_id
            formatted = None
            try:
                formatted = logs.format_channel(channel)  # type: ignore[arg-type]
            except Exception:
                formatted = None
            if formatted:
                extra.setdefault("channel", formatted)

        await self._ensure_error_notice(interaction)
        logs.log_view_error(
            interaction,
            self,
            error,
            tag=WELCOME_PANEL_TAG,
            extra=extra,
        )

    async def _notify_restart(self, interaction: discord.Interaction) -> None:
        """Acknowledge the restart interaction without a confusing toast."""

        if interaction.response.is_done():
            return
        try:
            await _defer_interaction(interaction)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to defer restart notice", exc_info=True)


class OnboardWizard(discord.ui.View):
    def __init__(self, controller: _ControllerProtocol, thread_id: int, *, step: int = 0) -> None:
        super().__init__(timeout=600)
        self.controller = controller
        self.thread_id = thread_id
        self.step = step
        self.message: discord.Message | None = None
        self._configure_components()

    def attach(self, message: discord.Message) -> None:
        self.message = message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - network
        checker = getattr(self.controller, "check_interaction", None)
        if callable(checker):
            try:
                allowed, _ = await checker(self.thread_id, interaction)
            except Exception:
                log.warning("inline wizard gate check failed", exc_info=True)
                return False
            return allowed
        return True

    def _questions(self) -> Sequence[Any]:
        questions_dict = getattr(self.controller, "questions_by_thread", {})
        if isinstance(questions_dict, dict):
            questions = questions_dict.get(self.thread_id) or []
            if isinstance(questions, Sequence):
                return questions
        return []

    def _question(self) -> Any | None:
        questions = list(self._questions())
        if not questions:
            return None
        if self.step < 0:
            self.step = 0
        if self.step >= len(questions):
            self.step = len(questions) - 1
        if self.step < 0 or self.step >= len(questions):
            return None
        return questions[self.step]

    def _question_label(self, question: Any | None) -> str:
        if question is None:
            return ""
        if isinstance(question, dict):
            return str(question.get("label") or question.get("text") or "")
        return str(getattr(question, "label", ""))

    def _question_type(self, question: Any | None) -> str:
        if question is None:
            return ""
        if isinstance(question, dict):
            value = question.get("type") or ""
        else:
            value = getattr(question, "type", "")
        return str(value or "")

    def _question_required(self, question: Any | None) -> bool:
        if question is None:
            return False
        if isinstance(question, dict):
            return bool(question.get("required"))
        return bool(getattr(question, "required", False))

    def _question_options(self, question: Any | None) -> Sequence[Any]:
        if question is None:
            return []
        if isinstance(question, dict):
            raw = question.get("options") or question.get("choices") or []
        else:
            raw = getattr(question, "options", [])
        if isinstance(raw, Sequence):
            return raw
        return []

    def _is_multi_select(self, question: Any | None) -> bool:
        if question is None:
            return False
        qtype = self._question_type(question)
        if qtype == "multi-select":
            return True
        multi_max = getattr(question, "multi_max", None)
        if multi_max:
            try:
                return int(multi_max) > 1
            except (TypeError, ValueError):
                return False
        if isinstance(question, dict):
            try:
                return int(question.get("multi_max") or 0) > 1
            except (TypeError, ValueError):
                return False
        return False

    def _question_key(self, question: Any | None) -> str:
        key_getter = getattr(self.controller, "_question_key", None)
        if callable(key_getter):
            return key_getter(question)  # type: ignore[arg-type]
        if isinstance(question, dict):
            value = question.get("id") or question.get("qid")
            return str(value or "")
        return str(getattr(question, "qid", ""))

    def _current_answer(self, question: Any | None) -> Any:
        key = self._question_key(question)
        accessor = getattr(self.controller, "_answer_for", None)
        if callable(accessor) and key:
            try:
                return accessor(self.thread_id, key)
            except Exception:
                log.debug("failed to read stored answer", exc_info=True)
        answers = getattr(self.controller, "answers_by_thread", {})
        if isinstance(answers, dict):
            thread_answers = answers.get(self.thread_id, {})
            if isinstance(thread_answers, dict):
                return thread_answers.get(key)
        return None

    def _selected_tokens(self, stored: Any) -> set[str]:
        if stored is None:
            return set()
        tokens: set[str] = set()
        if isinstance(stored, dict):
            value = stored.get("value")
            if value:
                tokens.add(str(value))
            values = stored.get("values")
            if isinstance(values, Iterable):
                for item in values:
                    if isinstance(item, dict):
                        token = item.get("value") or item.get("label")
                        if token:
                            tokens.add(str(token))
                    elif item:
                        tokens.add(str(item))
            return tokens
        if isinstance(stored, Iterable) and not isinstance(stored, (str, bytes)):
            for item in stored:
                if isinstance(item, dict):
                    token = item.get("value") or item.get("label")
                    if token:
                        tokens.add(str(token))
                elif item:
                    tokens.add(str(item))
        return tokens

    def _text_default(self, question: Any | None) -> str:
        stored = self._current_answer(question)
        if stored is None:
            return ""
        if isinstance(stored, str):
            return stored
        if isinstance(stored, (int, float)):
            return str(stored)
        return ""

    def _has_current_answer(self, question: Any | None) -> bool:
        if question is None:
            return False
        checker = getattr(self.controller, "has_answer", None)
        if callable(checker):
            try:
                return bool(checker(self.thread_id, question))
            except Exception:
                log.debug("inline wizard answer check failed", exc_info=True)
                return False
        stored = self._current_answer(question)
        if stored is None:
            return False
        if isinstance(stored, str):
            return bool(stored.strip())
        if isinstance(stored, (int, float)):
            return True
        if isinstance(stored, dict):
            return bool(stored)
        if isinstance(stored, Iterable):
            return any(True for _ in stored)
        return bool(stored)

    def _configure_components(self) -> None:
        self.clear_items()
        question = self._question()
        if question is None:
            self.add_item(self.CancelButton(self))
            return
        options = list(self._question_options(question))
        if options:
            select = self.OptionSelect(self, question, options, self._is_multi_select(question))
            self.add_item(select)
        else:
            self.add_item(self.TextPromptButton(self, question))
        self.add_item(self.BackButton(self))
        self.add_item(self.NextButton(self, question))
        self.add_item(self.CancelButton(self))

    def is_last_step(self) -> bool:
        questions = self._questions()
        return self.step >= len(questions) - 1

    async def refresh(self, interaction: discord.Interaction | None = None) -> None:
        self._configure_components()
        content = self.controller.render_step(self.thread_id, self.step)
        if interaction is not None:
            response = getattr(interaction, "response", None)
            if response is not None:
                is_done = getattr(response, "is_done", None)
                done = False
                if callable(is_done):
                    try:
                        done = bool(is_done())
                    except Exception:
                        done = False
                elif isinstance(is_done, bool):
                    done = is_done
                if not done:
                    try:
                        await interaction.response.edit_message(content=content, view=self)
                        return
                    except Exception:
                        log.warning("failed to edit wizard message via interaction", exc_info=True)
        if self.message is not None:
            try:
                await self.message.edit(content=content, view=self)
            except Exception:
                log.warning("failed to refresh wizard message", exc_info=True)

    async def on_timeout(self) -> None:  # pragma: no cover - network
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True  # type: ignore[assignment]
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except Exception:
                log.warning("failed to disable wizard on timeout", exc_info=True)
        self.stop()

    class OptionSelect(discord.ui.Select):
        def __init__(
            self,
            parent: "OnboardWizard",
            question: Any,
            options: Sequence[Any],
            is_multi: bool,
        ) -> None:
            self._wizard = parent
            self.question = question
            stored = parent._current_answer(question)
            selected = parent._selected_tokens(stored)
            select_options: list[discord.SelectOption] = []
            for option in options:
                if isinstance(option, dict):
                    label = str(option.get("label") or option.get("value") or "")
                    value = str(option.get("value") or option.get("label") or label)
                else:
                    label = str(getattr(option, "label", ""))
                    value = str(getattr(option, "value", label))
                select_options.append(
                    discord.SelectOption(label=label, value=value, default=value in selected)
                )
            placeholder = parent._question_label(question) or "Select an option"
            max_values = 1
            if is_multi:
                try:
                    configured = getattr(question, "multi_max", None)
                    if isinstance(question, dict):
                        configured = question.get("multi_max", configured)
                    if configured:
                        max_values = max(1, int(configured))
                    else:
                        max_values = max(1, len(select_options))
                except (TypeError, ValueError):
                    max_values = max(1, len(select_options))
            super().__init__(
                placeholder=placeholder,
                min_values=0,
                max_values=max_values,
                options=select_options,
            )

        async def callback(self, interaction: discord.Interaction) -> None:
            await self._wizard._handle_select(interaction, self.question, list(self.values))

    class TextPromptButton(discord.ui.Button):
        def __init__(self, parent: "OnboardWizard", question: Any) -> None:
            super().__init__(style=discord.ButtonStyle.secondary, label="Enter answer")
            self._wizard = parent
            self.question = question

        async def callback(self, interaction: discord.Interaction) -> None:
            await self._wizard._prompt_text_answer(interaction, self.question)

    class BackButton(discord.ui.Button):
        def __init__(self, parent: "OnboardWizard") -> None:
            super().__init__(style=discord.ButtonStyle.secondary, label="Back")
            self._wizard = parent
            if parent.step <= 0:
                self.disabled = True

        async def callback(self, interaction: discord.Interaction) -> None:
            wizard = self._wizard
            if wizard.step > 0:
                wizard.step -= 1
            await wizard.refresh(interaction)

    class NextButton(discord.ui.Button):
        def __init__(self, parent: "OnboardWizard", question: Any) -> None:
            label = "Finish" if parent.is_last_step() else "Next"
            super().__init__(style=discord.ButtonStyle.primary, label=label)
            self._wizard = parent
            required = parent._question_required(question)
            if required and not parent._has_current_answer(question):
                self.disabled = True

        async def callback(self, interaction: discord.Interaction) -> None:
            wizard = self._wizard
            next_index = wizard.step + 1
            total = len(wizard._questions())
            is_finished = False
            checker = getattr(wizard.controller, "is_finished", None)
            if callable(checker):
                try:
                    is_finished = bool(checker(wizard.thread_id, next_index))
                except Exception:
                    log.warning("inline wizard finish check failed", exc_info=True)
                    is_finished = next_index >= total
            else:
                is_finished = next_index >= total
            if is_finished:
                await wizard.controller.finish_inline_wizard(
                    wizard.thread_id,
                    interaction,
                    message=wizard.message,
                )
                wizard.stop()
                return
            wizard.step = next_index
            await wizard.refresh(interaction)

    class CancelButton(discord.ui.Button):
        def __init__(self, parent: "OnboardWizard") -> None:
            super().__init__(style=discord.ButtonStyle.danger, label="Cancel")
            self._wizard = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            wizard = self._wizard
            answers = getattr(wizard.controller, "answers_by_thread", None)
            if isinstance(answers, dict):
                answers.pop(wizard.thread_id, None)
            notice = "❌ Wizard cancelled."
            response = getattr(interaction, "response", None)
            handled = False
            if response is not None and not response.is_done():
                try:
                    await interaction.response.edit_message(content=notice, view=None)
                    handled = True
                except Exception:
                    handled = False
            if not handled and wizard.message is not None:
                try:
                    await wizard.message.edit(content=notice, view=None)
                except Exception:
                    log.warning("failed to update wizard cancel message", exc_info=True)
            wizard.stop()

    async def _prompt_text_answer(self, interaction: discord.Interaction, question: Any) -> None:
        controller = self.controller
        client = getattr(controller, "bot", None) or getattr(interaction, "client", None)
        if client is None:
            log.warning("inline wizard text prompt missing client")
            followup = getattr(interaction, "followup", None)
            try:
                if followup is not None:
                    await followup.send(
                        "⚠️ Can’t capture that answer right now. Please press **Enter answer** again.",
                        ephemeral=True,
                    )
                elif not interaction.response.is_done():
                    await interaction.response.send_message(
                        "⚠️ Can’t capture that answer right now. Please press **Enter answer** again.",
                        ephemeral=True,
                    )
            except Exception:
                log.warning("failed to notify user about inline text capture error", exc_info=True)
            return

        label = self._question_label(question) or "this question"
        prompt = f"✍️ Please type your answer for **{label}** below."
        prompt_message: discord.Message | None = None
        used_original = False
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(prompt, ephemeral=True)
                used_original = True
            else:
                followup = getattr(interaction, "followup", None)
                if followup is None:
                    log.warning("inline wizard followup handler missing for text prompt")
                    return
                prompt_message = await followup.send(prompt, ephemeral=True)
        except Exception:
            log.warning("failed to send inline text prompt", exc_info=True)
            return

        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        raw_thread_id = getattr(thread, "id", None)
        try:
            thread_id = int(raw_thread_id) if raw_thread_id is not None else int(self.thread_id)
        except (TypeError, ValueError):
            thread_id = int(self.thread_id)
        user = getattr(interaction, "user", None)
        raw_user_id = getattr(user, "id", None)
        try:
            user_id = int(raw_user_id) if raw_user_id is not None else None
        except (TypeError, ValueError):
            user_id = None
        if user_id is None:
            log.warning("inline wizard text prompt missing user context")
            return

        def check(message: discord.Message) -> bool:
            author = getattr(message, "author", None)
            channel = getattr(message, "channel", None)
            if author is None or getattr(author, "id", None) != user_id:
                return False
            if not isinstance(channel, discord.Thread):
                return False
            return int(getattr(channel, "id", 0) or 0) == thread_id

        try:
            message = await client.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            notice = "⏳ Timed out waiting for your answer. Press **Enter answer** to try again."
            try:
                if used_original:
                    await interaction.edit_original_response(content=notice)
                elif prompt_message is not None:
                    await prompt_message.edit(content=notice)
            except Exception:
                log.debug("failed to update timeout notice", exc_info=True)
            return
        except Exception:
            log.warning("inline wizard text capture failed", exc_info=True)
            return

        value = (message.content or "").strip()
        try:
            await message.delete()
        except Exception:
            log.debug("failed to delete inline text answer message", exc_info=True)

        required = self._question_required(question)
        key = self._question_key(question)
        meta_getter = getattr(controller, "_question_meta", None)
        if callable(meta_getter):
            meta = meta_getter(question)
        else:
            meta = {
                "qid": key,
                "label": self._question_label(question),
                "type": self._question_type(question),
                "validate": getattr(question, "validate", None)
                if not isinstance(question, dict)
                else question.get("validate"),
                "help": getattr(question, "help", None)
                if not isinstance(question, dict)
                else question.get("help"),
            }

        if required and not value:
            sender = getattr(controller, "_send_validation_error", None)
            if callable(sender):
                await sender(interaction, self.thread_id, meta, "This question is required.")
            else:
                warning = f"⚠️ **{self._question_label(question)}** is required."
                try:
                    if used_original:
                        await interaction.edit_original_response(content=warning)
                    elif prompt_message is not None:
                        await prompt_message.edit(content=warning)
                except Exception:
                    log.debug("failed to send required notice", exc_info=True)
            return

        if value:
            validator = getattr(controller, "validate_answer", None)
            if callable(validator):
                ok, cleaned, err = validator(meta, value)
            else:
                ok, cleaned, err = True, value, None
            if not ok:
                sender = getattr(controller, "_send_validation_error", None)
                if callable(sender):
                    await sender(interaction, self.thread_id, meta, err)
                else:
                    notice = err or "Input does not match the required format."
                    try:
                        if used_original:
                            await interaction.edit_original_response(content=f"⚠️ {notice}")
                        elif prompt_message is not None:
                            await prompt_message.edit(content=f"⚠️ {notice}")
                    except Exception:
                        log.debug("failed to send validation notice", exc_info=True)
                return
            if diag.is_enabled():
                checker = getattr(controller, "_has_sheet_regex", None)
                if callable(checker):
                    has_regex = checker(meta)
                else:
                    validate_field = (meta.get("validate") or "").strip().lower()
                    has_regex = validate_field.startswith("regex:")
                await diag.log_event(
                    "info",
                    "welcome_validator_branch",
                    qid=meta.get("qid"),
                    have_regex=has_regex,
                    type=meta.get("type"),
                )
            await controller.set_answer(self.thread_id, key, cleaned)
            success_notice = "✅ Saved."
        else:
            await controller.set_answer(self.thread_id, key, None)
            success_notice = "✅ Answer cleared."

        try:
            if used_original:
                await interaction.edit_original_response(content=success_notice)
            elif prompt_message is not None:
                await prompt_message.edit(content=success_notice)
        except Exception:
            log.debug("failed to post success notice", exc_info=True)

        await self.refresh()

    async def _handle_select(
        self,
        interaction: discord.Interaction,
        question: Any,
        selections: list[str],
    ) -> None:
        key = self._question_key(question)
        if not selections:
            await self.controller.set_answer(self.thread_id, key, None)
            await self.refresh(interaction)
            return
        options: dict[str, str] = {}
        for option in self._question_options(question):
            if isinstance(option, dict):
                label = str(option.get("label") or option.get("value") or "")
                value = str(option.get("value") or option.get("label") or label)
            else:
                label = str(getattr(option, "label", ""))
                value = str(getattr(option, "value", label))
            options[value] = label
        if self._is_multi_select(question):
            stored: list[dict[str, str]] = []
            for token in selections:
                label = options.get(token, token)
                stored.append({"value": token, "label": label})
            await self.controller.set_answer(self.thread_id, key, stored)
        else:
            token = selections[0]
            label = options.get(token, token)
            await self.controller.set_answer(
                self.thread_id,
                key,
                {"value": token, "label": label},
            )
        await self.refresh(interaction)
