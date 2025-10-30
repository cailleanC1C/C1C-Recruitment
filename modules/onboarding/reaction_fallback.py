"""Fallback handler for onboarding reaction triggers."""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import logs
from modules.onboarding import thread_scopes
from modules.onboarding.ui import panels
from modules.onboarding.welcome_flow import start_welcome_dialog

# Fallback: 🎫 on the Ticket Tool close-button message
FALLBACK_EMOJI = "🎫"  # :ticket:
TRIGGER_TOKEN = "[#welcome:ticket]"


def normalize_spaces(value: str) -> str:
    return " ".join(value.split())


async def _log_reject(
    reason: str,
    *,
    member: discord.abc.User | discord.Member | None = None,
    thread: discord.Thread | None = None,
    parent_id: int | None = None,
) -> None:
    await logs.send_welcome_log(
        "warn",
        actor=logs.format_actor(member),
        trigger="emoji",
        emoji=FALLBACK_EMOJI,
        reason=reason,
        thread=logs.format_thread(getattr(thread, "id", None)),
        parent=logs.format_parent(parent_id),
    )


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
            logging.info(
                "welcome.emoji.start %s",
                {"rejected": "disabled", "emoji": str(payload.emoji)},
            )
            await _log_reject("disabled")
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
            except Exception:
                logging.info(
                    "welcome.emoji.start %s",
                    {
                        "rejected": "member_fetch_failed",
                        "emoji": FALLBACK_EMOJI,
                        "user_id": payload.user_id,
                    },
                )
                return

        if not isinstance(member, discord.Member):
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "member_type",
                    "emoji": FALLBACK_EMOJI,
                    "user_id": payload.user_id,
                },
            )
            return

        if getattr(member, "bot", False):
            logging.info(
                "welcome.emoji.start %s",
                {"rejected": "bot_member", "emoji": FALLBACK_EMOJI, "user_id": member.id},
            )
            return

        thread: Optional[discord.Thread] = guild.get_thread(payload.channel_id)
        if thread is None:
            channel = self.bot.get_channel(payload.channel_id)
            if isinstance(channel, discord.Thread):
                thread = channel
            else:
                try:
                    channel = await self.bot.fetch_channel(payload.channel_id)
                except Exception:
                    logging.info(
                        "welcome.emoji.start %s",
                        {
                            "rejected": "channel_fetch_failed",
                            "emoji": FALLBACK_EMOJI,
                            "channel_id": payload.channel_id,
                        },
                    )
                    return
                if isinstance(channel, discord.Thread):
                    thread = channel
        if thread is None:
            return

        if not (
            thread_scopes.is_welcome_parent(thread)
            or thread_scopes.is_promo_parent(thread)
        ):
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "wrong_scope:parent",
                    "emoji": FALLBACK_EMOJI,
                    "thread_id": thread.id,
                },
            )
            await _log_reject(
                "wrong_scope",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
            )
            return

        if not (rbac.is_admin_member(member) or rbac.is_recruiter(member)):
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "role_gate",
                    "emoji": FALLBACK_EMOJI,
                    "user_id": member.id,
                    "thread_id": thread.id,
                },
            )
            await _log_reject(
                "role_gate",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
            )
            return

        try:
            message = await thread.fetch_message(payload.message_id)
        except Exception:
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "fetch_failed",
                    "emoji": FALLBACK_EMOJI,
                    "thread_id": thread.id,
                    "message_id": payload.message_id,
                },
            )
            await _log_reject(
                "fetch_failed",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
            )
            return

        content = (getattr(message, "content", "") or "")
        content_lower = normalize_spaces(content.lower())

        match: Optional[str] = None
        if TRIGGER_TOKEN in content:
            match = "token"
        elif "by reacting with" in content_lower:
            match = "phrase"
        elif rbac.is_admin_member(member):
            match = "override"
        else:
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "no_token_or_phrase",
                    "emoji": FALLBACK_EMOJI,
                    "thread_id": thread.id,
                    "message_id": message.id,
                },
            )
            await _log_reject(
                "no_token_or_phrase",
                member=member,
                thread=thread,
                parent_id=getattr(thread, "parent_id", None),
            )
            return

        logging.info(
            "welcome.emoji.start %s",
            {
                "emoji": FALLBACK_EMOJI,
                "thread_id": thread.id,
                "message_id": message.id,
                "user_id": member.id,
                "match": match,
            },
        )

        bot_user_id = getattr(getattr(self.bot, "user", None), "id", None)
        existing_panel = await _find_panel_message(thread, bot_user_id=bot_user_id)
        if existing_panel is not None:
            if panels.is_panel_live(existing_panel.id):
                await logs.send_welcome_log(
                    "warn",
                    actor=logs.format_actor(member),
                    trigger="emoji",
                    reason="deduped",
                    thread=logs.format_thread(thread.id),
                )
                return
            await logs.send_welcome_log(
                "info",
                actor=logs.format_actor(member),
                trigger="emoji",
                emoji=FALLBACK_EMOJI,
                flow="welcome",
                result="restarted",
                thread=logs.format_thread(thread.id),
                parent=logs.format_parent(getattr(thread, "parent_id", None)),
            )
            try:
                await existing_panel.delete()
            except Exception:
                logging.warning(
                    "failed to delete expired welcome panel",
                    exc_info=True,
                    extra={"thread_id": thread.id},
                )
            panels.mark_panel_inactive_by_message(existing_panel.id)
        else:
            await logs.send_welcome_log(
                "info",
                actor=logs.format_actor(member),
                trigger="emoji",
                emoji=FALLBACK_EMOJI,
                flow="welcome",
                scope="close_message",
                match=logs.format_match(match),
                result="started",
                thread=logs.format_thread(thread.id),
                parent=logs.format_parent(getattr(thread, "parent_id", None)),
            )

        await start_welcome_dialog(thread, member, source="emoji", bot=self.bot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingReactionFallbackCog(bot))
