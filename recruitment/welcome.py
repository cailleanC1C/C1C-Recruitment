from __future__ import annotations

from typing import Any, Dict, Optional

from discord.ext import commands

from shared import runtime as rt
from shared.config import LOG_CHANNEL_ID
from shared.coreops_rbac import is_admin_member, is_staff_member
from sheets.recruitment import get_cached_welcome_templates


def staff_only() -> commands.check:
    """
    Allow staff/admin via CoreOps roles. Also allow Discord 'Administrator'
    permission as fallback (useful on fresh/dev guilds).
    """

    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        if is_staff_member(author) or is_admin_member(author):
            return True

        perms = getattr(getattr(author, "guild_permissions", None), "administrator", False)
        return bool(perms)

    return commands.check(predicate)


class WelcomeBridge(commands.Cog):
    """Recruitment welcome command backed by cached Sheets templates."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="welcome")
    @staff_only()
    async def welcome(
        self,
        ctx: commands.Context,
        clan: Optional[str] = None,
        *,
        note: Optional[str] = None,
    ) -> None:
        """Render and post a templated welcome message."""

        templates = get_cached_welcome_templates()
        if not templates:
            await ctx.send("⚠️ No welcome templates found. Try again after the next refresh.")
            return

        tag = (clan or "").strip().upper()
        row: Optional[Dict[str, Any]] = None
        for candidate in templates:
            candidate_tag = str(candidate.get("ClanTag", "")).strip().upper()
            if candidate_tag == tag:
                row = candidate
                break

        if not row:
            await ctx.send(f"⚠️ No template configured for clan tag `{tag}`.")
            return

        text = str(row.get("Message", "")).strip()
        if not text:
            await ctx.send(f"⚠️ Template for `{tag}` is missing a 'Message' field.")
            return

        if note:
            text = f"{text}\n\n{note}"

        await ctx.send(text)

        if LOG_CHANNEL_ID:
            try:
                channel_name = getattr(ctx.channel, "name", "?")
                await rt.send_log_message(
                    f"[welcome] actor={ctx.author} clan={tag or '—'} channel=#{channel_name}"
                )
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeBridge(bot))
