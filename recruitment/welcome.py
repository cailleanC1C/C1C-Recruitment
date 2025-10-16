from __future__ import annotations
from typing import Any, Dict, Optional
from discord.ext import commands

from shared import runtime as rt
# NOTE: Do not import role ID constants from shared.config; not exported here.
from shared.coreops_rbac import is_staff_member, is_admin_member
from sheets.recruitment import get_cached_welcome_templates

# --- RBAC decorator (staff with fallback) -------------------------------------
def staff_only():
    """
    Allow staff/admin via CoreOps roles. Also allow Discord 'Administrator'
    permission as fallback (useful on fresh/dev guilds without CoreOps roles).
    """
    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        # CoreOps roles OR server Administrator (fallback)
        if is_staff_member(author) or is_admin_member(author):
            return True
        perms = getattr(getattr(author, "guild_permissions", None), "administrator", False)
        return bool(perms)
    return commands.check(predicate)

class WelcomeBridge(commands.Cog):
    """
    Recruitment welcome command using cached templates.
    Behavior matches legacy: it renders a template row and posts to the target channel.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="welcome")
    @staff_only()
    async def welcome(self, ctx: commands.Context, clan: Optional[str] = None, *, note: Optional[str] = None):
        """
        Post a templated welcome. Template rows are read from the cached 'templates' bucket.
        Usage: !welcome <CLAN_TAG> [note...]
        """
        templates = get_cached_welcome_templates()
        if not templates:
            await ctx.send("⚠️ No welcome templates found. Try again after the next refresh.")
            return

        tag = (clan or "").strip().upper()
        row: Optional[Dict[str, Any]] = None
        for r in templates:
            rtag = str(r.get("ClanTag", "")).strip().upper()
            if rtag == tag:
                row = r
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

        # Unified log line
        try:
            await rt.send_log_message(f"[welcome] actor={ctx.author} clan={tag} channel=#{getattr(ctx.channel, 'name', '?')}")
        except Exception:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeBridge(bot))
