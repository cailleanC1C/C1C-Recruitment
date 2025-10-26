"""Prefix command wiring for the restored legacy member clan search."""

from __future__ import annotations

from discord.ext import commands

from modules.recruitment.views.member_panel_legacy import MemberPanelControllerLegacy


class RecruitmentMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctrl = MemberPanelControllerLegacy(bot)

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(name="clansearch")
    async def clansearch(
        self, ctx: commands.Context, *, extra: str | None = None
    ) -> None:
        """Launch the member search panel (no arguments allowed)."""

        if extra and extra.strip():
            await ctx.reply(
                "❌ `!clansearch` doesn’t take a clan tag or name.\n"
                "• Use **`!clan <tag or name>`** to see a specific clan profile (e.g., `!clan C1CE`).\n"
                "• Or type **`!clansearch`** by itself to open the filter panel.",
                mention_author=False,
            )
            return

        await self.ctrl.open(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecruitmentMember(bot))

