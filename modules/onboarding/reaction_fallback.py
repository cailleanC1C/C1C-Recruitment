"""Fallback handler for onboarding reaction triggers."""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import thread_scopes
from modules.onboarding.welcome_flow import start_welcome_dialog

# Fallback: 🎫 on the Ticket Tool close-button message
FALLBACK_EMOJI = "🎫"  # :ticket:
TRIGGER_PHRASE = "poke it awake by reacting with 🎫"
TRIGGER_TOKEN = "[#welcome:ticket]"


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
            return

        if str(payload.emoji) != FALLBACK_EMOJI:
            return

        bot_user = getattr(self.bot, "user", None)
        if bot_user and payload.user_id == bot_user.id:
            logging.info(
                "welcome.emoji.start %s",
                {"rejected": "self_reaction", "emoji": FALLBACK_EMOJI},
            )
            return

        if payload.guild_id is None:
            logging.info(
                "welcome.emoji.start %s",
                {"rejected": "no_guild_id", "emoji": FALLBACK_EMOJI},
            )
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            logging.info(
                "welcome.emoji.start %s",
                {"rejected": "no_guild", "emoji": FALLBACK_EMOJI},
            )
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
            logging.info(
                "welcome.emoji.start %s",
                {
                    "rejected": "wrong_scope:not_thread",
                    "emoji": FALLBACK_EMOJI,
                    "channel_id": payload.channel_id,
                },
            )
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
            return

        content = (getattr(message, "content", "") or "").strip()
        match_details: Optional[dict[str, str]] = None
        if TRIGGER_TOKEN in content:
            match_details = {"match": "token", "token": TRIGGER_TOKEN}
        elif TRIGGER_PHRASE in content:
            match_details = {"match": "phrase", "needle": TRIGGER_PHRASE}
        elif rbac.is_admin_member(member):
            match_details = {"match": "override", "by_role": "admin"}
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
            return

        assert match_details is not None

        logging.info(
            "welcome.emoji.start %s",
            {
                "emoji": FALLBACK_EMOJI,
                "thread_id": thread.id,
                "message_id": message.id,
                "user_id": member.id,
                **match_details,
            },
        )

        await start_welcome_dialog(thread, member, source="emoji", bot=self.bot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingReactionFallbackCog(bot))
