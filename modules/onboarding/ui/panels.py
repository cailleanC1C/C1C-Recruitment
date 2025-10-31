"""Persistent UI components for the onboarding welcome panel."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import discord

from c1c_coreops import rbac

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


def _claim_interaction(interaction: discord.Interaction) -> bool:
    if getattr(interaction, "_c1c_claimed", False):
        return False
    setattr(interaction, "_c1c_claimed", True)
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


class OpenQuestionsPanelView(discord.ui.View):
    """Persistent panel view that launches the welcome modal flow."""

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
        state = diag.interaction_state(interaction)
        controller = self._controller
        thread_id = state.get("thread_id")
        target_user_id: int | None = None
        if controller is not None and thread_id is not None:
            getter = getattr(controller, "diag_target_user_id", None)
            if callable(getter):
                target_user_id = getter(int(thread_id))
        if diag.is_enabled():
            await diag.log_event(
                "info",
                "panel_button_clicked",
                custom_id=OPEN_QUESTIONS_CUSTOM_ID,
                target_user_id=target_user_id,
                ambiguous_target=target_user_id is None,
                **state,
            )

        if not _claim_interaction(interaction):
            return

        channel = getattr(interaction, "channel", None)
        thread = channel if isinstance(channel, discord.Thread) else None
        controller, thread_id = self._resolve(interaction)
        message = getattr(interaction, "message", None)
        message_id = getattr(message, "id", None)
        actor_id = getattr(interaction.user, "id", None)

        snapshot, permissions_text, missing = diag.permission_snapshot(interaction)

        controller_context: dict[str, Any] = {
            "view": "panel",
            "view_tag": WELCOME_PANEL_TAG,
            "custom_id": OPEN_QUESTIONS_CUSTOM_ID,
            "view_id": OPEN_QUESTIONS_CUSTOM_ID,
            "app_permissions": permissions_text,
            "app_permissions_snapshot": snapshot,
        }
        if thread_id is not None:
            try:
                controller_context["thread_id"] = int(thread_id)
            except (TypeError, ValueError):
                pass
        if message_id is not None:
            try:
                controller_context["message_id"] = int(message_id)
            except (TypeError, ValueError):
                pass
        if actor_id is not None:
            try:
                controller_context["actor_id"] = int(actor_id)
            except (TypeError, ValueError):
                pass
        if isinstance(thread, discord.Thread):
            parent_id = getattr(thread, "parent_id", None)
            if parent_id is not None:
                try:
                    controller_context["parent_channel_id"] = int(parent_id)
                except (TypeError, ValueError):
                    pass
        else:
            parent_id = None

        log_context: dict[str, Any] = {
            **logs.thread_context(thread),
            "view": "panel",
            "view_tag": WELCOME_PANEL_TAG,
            "custom_id": OPEN_QUESTIONS_CUSTOM_ID,
            "view_id": OPEN_QUESTIONS_CUSTOM_ID,
            "actor": logs.format_actor(interaction.user),
            "app_permissions": permissions_text,
            "app_permissions_snapshot": snapshot,
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            log_context["actor_name"] = actor_name
        if thread_id is not None and "thread" not in log_context:
            log_context["thread"] = logs.format_thread(thread_id)
        if thread_id is not None:
            try:
                log_context["thread_id"] = int(thread_id)
            except (TypeError, ValueError):
                pass
        if message_id is not None:
            try:
                log_context["message_id"] = int(message_id)
            except (TypeError, ValueError):
                pass
        if actor_id is not None:
            try:
                log_context["actor_id"] = int(actor_id)
            except (TypeError, ValueError):
                pass
        if parent_id is not None:
            try:
                log_context["parent_channel_id"] = int(parent_id)
            except (TypeError, ValueError):
                pass

        if controller is None or thread_id is None:
            await self._restart_from_view(interaction, log_context)
            return

        actor = interaction.user
        actor_id = getattr(actor, "id", None)
        actor_is_target = (
            target_user_id is not None
            and actor_id is not None
            and int(actor_id) == int(target_user_id)
        )
        actor_is_privileged = bool(rbac.is_admin_member(actor) or rbac.is_recruiter(actor))
        can_use = actor_is_target or actor_is_privileged

        if not can_use:
            notice = "⚠️ This panel is reserved for the recruit and authorized recruiters."
            result = "ambiguous_target" if target_user_id is None else "denied_role"
            extra: dict[str, Any] = {}
            if result == "denied_role":
                extra["reason"] = "missing_roles"
            await logs.send_welcome_log("warn", result=result, **log_context, **extra)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(notice, ephemeral=True)
                else:
                    await interaction.response.send_message(notice, ephemeral=True)
            except Exception:  # pragma: no cover - defensive logging
                log.warning("failed to send panel access notice", exc_info=True)
            return

        if missing:
            await logs.send_welcome_log(
                "warn",
                result="denied_perms",
                missing=";".join(sorted(missing)),
                **log_context,
            )
            await self._notify_missing_permissions(interaction)
            return

        try:
            allowed, _ = await controller.check_interaction(
                thread_id,
                interaction,
                context=controller_context,
            )
            if not allowed:
                return
            await controller._handle_modal_launch(
                thread_id,
                interaction,
                context=controller_context,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            error_context = dict(log_context)
            await logs.send_welcome_exception("error", exc, **error_context)
            await self._notify_error(interaction)

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
        await logs.send_welcome_log("info", **restart_context)

        await self._notify_restart(interaction)

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

    async def _notify_error(self, interaction: discord.Interaction) -> None:
        message = "⚠️ Something went wrong while opening the onboarding panel. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send error notice", exc_info=True)

    async def _notify_restart(self, interaction: discord.Interaction) -> None:
        message = "♻️ Restarting the onboarding form…"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send restart notice", exc_info=True)

    async def _notify_missing_permissions(self, interaction: discord.Interaction) -> None:
        message = (
            "⚠️ I can't send messages in this thread yet. Please adjust the ticket permissions and try again."
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send permission notice", exc_info=True)
