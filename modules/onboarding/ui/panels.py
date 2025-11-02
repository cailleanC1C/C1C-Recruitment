"""Persistent UI components for the onboarding welcome panel."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, cast

import discord

from c1c_coreops import rbac  # Retained for compatibility with existing tests/hooks.
from modules.onboarding import diag, logs

__all__ = [
    "OPEN_QUESTIONS_CUSTOM_ID",
    "WELCOME_PANEL_TAG",
    "OpenQuestionsPanelView",
    "bind_controller",
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

    @discord.ui.button(
        label="Open questions",
        style=discord.ButtonStyle.primary,
        custom_id=OPEN_QUESTIONS_CUSTOM_ID,
    )
    async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Minimal button handler that always attempts to open the modal."""

        controller, thread_id = self._resolve(interaction)
        if controller is None or thread_id is None:
            await self._ensure_error_notice(interaction)
            return

        diag_state = diag.interaction_state(interaction)
        diag_state["thread_id"] = thread_id
        diag_state["custom_id"] = OPEN_QUESTIONS_CUSTOM_ID

        try:
            modal = controller.build_modal_stub(thread_id)
        except Exception:
            await self._ensure_error_notice(interaction)
            raise

        diag_state["modal_index"] = getattr(modal, "step_index", getattr(modal, "_c1c_index", 0))
        diag_state["modal_total"] = getattr(modal, "total_steps", None)

        try:
            await interaction.response.send_modal(modal)
        except discord.InteractionResponded:
            if diag.is_enabled():
                await diag.log_event(
                    "warning",
                    "modal_launch_skipped",
                    skip_reason="interaction_already_responded",
                    **diag_state,
                )
            return
        if diag.is_enabled():
            await diag.log_event("info", "modal_launch_sent", **diag_state)

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

    async def _handle_launch(self, interaction: discord.Interaction) -> None:
        await self.launch(interaction, cast(discord.ui.Button, None))

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
        message = "♻️ Restarting the onboarding form…"
        if interaction.response.is_done():
            await _edit_original_response(interaction, content=message)
            return
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send restart notice", exc_info=True)
