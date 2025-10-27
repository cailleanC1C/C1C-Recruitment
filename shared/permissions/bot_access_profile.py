"""Permission profile constants for the shared bot role overwrite."""

from __future__ import annotations

from typing import Dict

import discord

__all__ = [
    "DEFAULT_THREADS_ENABLED",
    "BOT_PERMISSION_MATRIX",
    "build_allow_overwrite",
    "build_deny_overwrite",
    "serialize_overwrite",
]

DEFAULT_THREADS_ENABLED = True

# The overwrite intentionally enumerates every flag we rely on so comparisons are stable.
BOT_PERMISSION_MATRIX: Dict[str, bool] = {
    "view_channel": True,
    "send_messages": True,
    "send_messages_in_threads": True,
    "create_public_threads": True,
    "create_private_threads": True,
    "manage_messages": True,
    "manage_threads": True,
    "embed_links": True,
    "attach_files": True,
    "add_reactions": True,
    "use_external_emojis": True,
    "use_external_stickers": True,
    "read_message_history": True,
    # Explicit denials for riskier capabilities follow.
    "mention_everyone": False,
    "manage_channels": False,
    "manage_permissions": False,
    "manage_webhooks": False,
    "create_instant_invite": False,
    "use_application_commands": False,
    "send_tts_messages": False,
    "send_voice_messages": False,
    "create_polls": False,
    "use_embedded_activities": False,
    "use_external_apps": False,
    "connect": False,
    "speak": False,
    "stream": False,
    "priority_speaker": False,
    "use_voice_activation": False,
    "request_to_speak": False,
    "mute_members": False,
    "deafen_members": False,
    "move_members": False,
    "manage_events": False,
}

# Stage moderator does not have a dedicated permission flag in discord.py 2.3.


def _build_overwrite(entries: Dict[str, bool]) -> discord.PermissionOverwrite:
    """Construct a permission overwrite using the provided truth table."""

    return discord.PermissionOverwrite(**entries)


def build_allow_overwrite(*, threads_enabled: bool = DEFAULT_THREADS_ENABLED) -> discord.PermissionOverwrite:
    """Return the overwrite applied when the bot role is allowed in a channel."""

    entries = dict(BOT_PERMISSION_MATRIX)
    if not threads_enabled:
        entries.update(
            {
                "send_messages_in_threads": False,
                "create_public_threads": False,
                "create_private_threads": False,
            }
        )
    return _build_overwrite(entries)


def build_deny_overwrite() -> discord.PermissionOverwrite:
    """Return the overwrite applied when the bot role is explicitly denied."""

    entries = {key: False for key in BOT_PERMISSION_MATRIX.keys()}
    entries["view_channel"] = False
    return _build_overwrite(entries)


def serialize_overwrite(overwrite: discord.PermissionOverwrite | None) -> str:
    """Serialize an overwrite to a stable string for audit rows."""

    if overwrite is None:
        return "missing"
    parts: list[str] = []
    for key, value in overwrite:
        if value is None:
            continue
        emoji = "✅" if value else "❌"
        parts.append(f"{emoji} {key}")
    return ", ".join(sorted(parts)) if parts else "empty"
