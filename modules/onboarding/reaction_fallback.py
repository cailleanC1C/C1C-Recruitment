"""Fallback handler for onboarding reaction triggers."""
from __future__ import annotations

from typing import Any, Optional

import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import logs, thread_scopes
from modules.onboarding.ui import panels
from modules.onboarding.welcome_flow import start_welcome_dialog

# Fallback: 🎫 on the Ticket Tool close-button message
FALLBACK_EMOJI = "🎫"  # :ticket:
TRIGGER_TOKEN = "[#welcome:ticket]"


def normalize_spaces(value: str) -> str:
    return " ".join(value.split())


def _base_context(
    *,
    member: discord.abc.User | discord.Member | None = None,
    thread: discord.Thread | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    context = logs.thread_context(thread)
    context["view"] = "panel"
    context["view_tag"] = panels.WELCOME_PANEL_TAG
    context["custom_id"] = "fallback.emoji"
    context["app_permissions"] = "-"
    context["app_permissions_snapshot"] = "-"
    if thread is not None:
        thread_id = getattr(thread, "id", None)
        if thread_id is not None:
            try:
                context["thread_id"] = int(thread_id)
            except (TypeError, ValueError):
                pass
        parent_id = getattr(thread, "parent_id", None)
        if parent_id is not None:
            try:
                context["parent_channel_id"] = int(parent_id)
            except (TypeError, ValueError):
                pass
    if member is not None:
        context["actor"] = logs.format_actor(member)
        actor_name = logs.format_actor_handle(member)
        if actor_name:
            context["actor_name"] = actor_name
    else:
        context["actor"] = f"<{user_id}>" if user_id else logs.format_actor(None)
    context["emoji"] = FALLBACK_EMOJI
    return context


async def _log_reject(
    reason: str,
    *,
    member: discord.abc.User | discord.Member | None = None,
    thread: discord.Thread | None = None,
    parent_id: int | None = None,
    trigger: str | None = None,
    result: str = "rejected",
    level: str = "warn",
) -> None:
    context = _base_context(member=member, thread=thread)
    if parent_id and "parent" not in context:
        context["parent"] = logs.format_parent(parent_id)
    context["result"] = result
    context["reason"] = reason
    context["trigger"] = trigger or "phrase_match"
    await logs.send_welcome_log(level, **context)


async def _find_panel_message(
    thread: discord.Thread,
    *,
    bot_user_id: int | None,
) -> Optional[discord.Message]:
    history = getattr(thread, "history", None)
    if bot_user_id is None or history is None or not callable(history):
        return None
    async for message in history(limit=20):
        author = getattr(message, "author", None)
        if author is None or getattr(author, "id", None) != bot_user_id:
            continue
        for row in getattr(message, "components", []) or []:
            for component in getattr(row, "children", []) or []:
                if getattr(component, "custom_id", None) == panels.OPEN_QUESTIONS_CUSTOM_ID:
                    return message
        for component in getattr(message, "components", []) or []:
            if getattr(component, "custom_id", None) == panels.OPEN_QUESTIONS_CUSTOM_ID:
                return message
    return None


class OnboardingReactionFallbackCog(commands.Cog):
    """Listen for onboarding fallback emoji reactions and trigger the dialog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        if not feature_flags.is_enabled("welcome_dialog"):
            await _log_reject(
                "disabled",
                trigger="feature_disabled",
                result="feature_disabled",
                level="info",
            )
            return

        if str(payload.emoji) != FALLBACK_EMOJI:
            return

        bot_user = getattr(self.bot, "user", None)
        if bot_user and payload.user_id == bot_user.id:
            return

        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member: Optional[discord.Member] = payload.member
        if member is None:
            member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception as exc:
                context = _base_context(user_id=payload.user_id)
                context.update({"result": "member_fetch_failed", "trigger": "member_lookup"})
                await logs.send_welcome_exception("warn", exc, **context)
                return

        if not isinstance(member, discord.Member):
            context = _base_context(user_id=payload.user_id)
            context.update({"result": "member_type", "trigger": "member_lookup"})
            await logs.send_welcome_log("warn", **context)
            return

        if getattr(member, "bot", False):
            context = _base_context(member=member, user_id=payload.user_id)
            context.update({"result": "bot_member", "trigger": "member_lookup"})
            await logs.send_welcome_log("info", **context)
            return

        thread: Optional[discord.Thread] = guild.get_thread(payload.channel_id)
        if thread is None:
            channel = self.bot.get_channel(payload.channel_id)
            if isinstance(channel, discord.Thread):
                thread = channel
            else:
                try:
                    channel = await self.bot.fetch_channel(payload.channel_id)
                except Exception as exc:
                    context = _base_context(member=member, user_id=payload.user_id)
                    context.update({"result": "channel_fetch_failed", "trigger": "channel_lookup"})
                    await logs.send_welcome_exception("warn", exc, **context)
                    return
                if isinstance(channel, discord.Thread):
                    thread = channel
        if thread is None:
            return

        if not thread_scopes.is_welcome_parent(thread):
            await _log_reject(
                "wrong_scope",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
                trigger="scope_gate",
                result="wrong_scope",
            )
            return

        if not (rbac.is_admin_member(member) or rbac.is_recruiter(member)):
            await _log_reject(
                "role_gate",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
                trigger="role_gate",
                result="role_gate",
            )
            return

        try:
            message = await thread.fetch_message(payload.message_id)
        except Exception as exc:
            context = _base_context(member=member, thread=thread)
            context.update({"result": "message_lookup_failed", "trigger": "message_lookup"})
            await logs.send_welcome_exception("warn", exc, **context)
            return

        content = (getattr(message, "content", "") or "")
        content_lower = normalize_spaces(content.lower())

        phrase_match = "by reacting with" in content_lower
        token_match = TRIGGER_TOKEN in content
        eligible = phrase_match or token_match

        if not eligible:
            await _log_reject(
                "no_trigger",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
                result="no_trigger",
                level="warn",
            )
            return

        trigger = "token_match" if token_match and not phrase_match else "phrase_match"

        context = _base_context(member=member, thread=thread)
        context.update({"trigger": trigger, "result": "emoji_received"})
        await logs.send_welcome_log("info", **context)

        bot_user_id = getattr(getattr(self.bot, "user", None), "id", None)
        existing_panel = await _find_panel_message(thread, bot_user_id=bot_user_id)
        if existing_panel is not None:
            if panels.is_panel_live(existing_panel.id):
                dedup_context = _base_context(member=member, thread=thread)
                dedup_context.update({"trigger": trigger, "result": "deduped"})
                await logs.send_welcome_log("warn", **dedup_context)
                return
            restart_context = _base_context(member=member, thread=thread)
            restart_context.update({"trigger": trigger, "result": "restarted"})
            await logs.send_welcome_log("info", **restart_context)
            try:
                await existing_panel.delete()
            except Exception as exc:
                await logs.send_welcome_exception("warn", exc, **restart_context)
            panels.mark_panel_inactive_by_message(existing_panel.id)
        else:
            start_context = _base_context(member=member, thread=thread)
            start_context.update({"trigger": trigger, "result": "started"})
            await logs.send_welcome_log("info", **start_context)

        try:
            await start_welcome_dialog(thread, member, source="emoji", bot=self.bot)
        except Exception as exc:
            failure_context = _base_context(member=member, thread=thread)
            failure_context.update({"trigger": trigger, "result": "launch_failed"})
            await logs.send_welcome_exception("error", exc, **failure_context)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingReactionFallbackCog(bot))
