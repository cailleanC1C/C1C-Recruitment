"""Recruitment welcome command registered under the cogs namespace."""

from __future__ import annotations

from typing import Any, Dict, Optional

from discord.ext import commands

from c1c_coreops.helpers import tier
from c1c_coreops.rbac import is_admin_member, is_staff_member
from modules.common import runtime as rt
from shared.sheets import async_facade as sheets


def staff_only():
    """Allow CoreOps staff/admin roles or Discord Administrator fallback."""

    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        if is_staff_member(author) or is_admin_member(author):
            return True
        if getattr(ctx, "_coreops_suppress_denials", False):
            raise commands.CheckFailure("Staff only.")
        try:
            await ctx.reply("Staff only.")
        except Exception:
            pass
        raise commands.CheckFailure("Staff only.")

    return commands.check(predicate)


class WelcomeBridge(commands.Cog):
    """Recruitment welcome command using cached templates."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @tier("staff")
    @commands.command(name="welcome", usage="[clan] @mention")
    @staff_only()
    async def welcome(
        self,
        ctx: commands.Context,
        clan: Optional[str] = None,
        *,
        note: Optional[str] = None,
    ) -> None:
        """Post a templated welcome message for the provided clan tag."""

        templates = await sheets.get_cached_welcome_templates()
        if not templates:
            await ctx.send("⚠️ No welcome templates found. Try again after the next refresh.")
            return

        tag = (clan or "").strip().upper()
        row: Optional[Dict[str, Any]] = None
        for entry in templates:
            rtag = str(entry.get("ClanTag", "")).strip().upper()
            if rtag == tag:
                row = entry
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

        try:
            await rt.send_log_message(
                f"[welcome] actor={ctx.author} clan={tag} channel=#{getattr(ctx.channel, 'name', '?')}"
            )
        except Exception:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeBridge(bot))
