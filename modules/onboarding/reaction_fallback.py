"""Fallback handler for onboarding reaction triggers."""
from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import thread_scopes
from modules.onboarding.welcome_flow import start_welcome_dialog

FALLBACK_EMOJI = "🧭"


class OnboardingReactionFallbackCog(commands.Cog):
    """Listen for onboarding fallback emoji reactions and trigger the dialog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        if not feature_flags.is_enabled("welcome_dialog"):
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
                return

        if not isinstance(member, discord.Member):
            return

        if getattr(member, "bot", False):
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
                    return
                if isinstance(channel, discord.Thread):
                    thread = channel
        if thread is None:
            return

        if not (
            thread_scopes.is_welcome_parent(thread)
            or thread_scopes.is_promo_parent(thread)
        ):
            return

        if not (rbac.is_admin_member(member) or rbac.is_recruiter(member)):
            return

        starter_message = await _resolve_thread_starter_message(thread)
        if starter_message is None:
            return
        if starter_message.id != payload.message_id:
            return

        await start_welcome_dialog(thread, member, source="emoji", bot=self.bot)


async def _resolve_thread_starter_message(
    thread: discord.Thread,
) -> Optional[discord.Message]:
    try:
        starter = getattr(thread, "starter_message", None)
        if starter is not None:
            return starter

        async for message in thread.history(limit=1, oldest_first=True):
            return message
    except asyncio.CancelledError:
        raise
    except Exception:
        return None
    return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingReactionFallbackCog(bot))
