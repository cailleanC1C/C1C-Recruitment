"""Persistent UI components for the onboarding welcome panel."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import discord

from modules.onboarding import logs

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


def _claim_interaction(interaction: discord.Interaction) -> bool:
    if getattr(interaction, "_c1c_claimed", False):
        return False
    setattr(interaction, "_c1c_claimed", True)
    return True


def _app_permission_snapshot(
    interaction: discord.Interaction,
) -> tuple[dict[str, bool], str, set[str]]:
    perms = getattr(interaction, "app_permissions", None)
    send_messages = bool(getattr(perms, "send_messages", False)) if perms is not None else False
    send_in_threads = (
        bool(getattr(perms, "send_messages_in_threads", False)) if perms is not None else False
    )
    embed_links = bool(getattr(perms, "embed_links", False)) if perms is not None else False
    read_history = bool(getattr(perms, "read_message_history", False)) if perms is not None else False

    snapshot = {
        "send_messages": send_messages,
        "send_messages_in_threads": send_in_threads,
        "embed_links": embed_links,
        "read_message_history": read_history,
    }
    formatted = ", ".join(f"{key}={value}" for key, value in snapshot.items())

    missing: set[str] = set()
    if not send_messages:
        missing.add("send_messages")
    channel = getattr(interaction, "channel", None)
    if isinstance(channel, discord.Thread) and not send_in_threads:
        missing.add("send_messages_in_threads")

    return snapshot, formatted, missing


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
    try:
        bot.add_view(OpenQuestionsPanelView())
    except Exception:  # pragma: no cover - defensive logging
        log.warning("failed to register persistent welcome panel view", exc_info=True)


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
        if not _claim_interaction(interaction):
            return

        channel = getattr(interaction, "channel", None)
        thread = channel if isinstance(channel, discord.Thread) else None
        controller, thread_id = self._resolve(interaction)
        message = getattr(interaction, "message", None)
        message_id = getattr(message, "id", None)
        actor_id = getattr(interaction.user, "id", None)

        snapshot, permissions_text, missing = _app_permission_snapshot(interaction)

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
            await logs.send_welcome_log(
                "warn",
                result="stale",
                reason="stale_controller",
                **log_context,
            )
            await self._notify_expired(interaction)
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
            await controller._handle_modal_launch(thread_id, interaction)
        except Exception as exc:  # pragma: no cover - defensive path
            error_context = dict(log_context)
            await logs.send_welcome_exception("error", exc, **error_context)
            await self._notify_error(interaction)

    async def _notify_expired(self, interaction: discord.Interaction) -> None:
        message = "⚠️ This onboarding panel expired. Please react again to restart."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send expired panel notice", exc_info=True)

    async def _notify_error(self, interaction: discord.Interaction) -> None:
        message = "⚠️ Something went wrong while opening the onboarding panel. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:  # pragma: no cover - defensive logging
            log.warning("failed to send error notice", exc_info=True)

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
