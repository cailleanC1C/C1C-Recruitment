"""Prefix command wiring for member-facing clan search."""

from __future__ import annotations

from discord.ext import commands

from modules.recruitment.views.member_panel import MemberPanelController


class RecruitmentMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctrl = MemberPanelController(bot)

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(name="clansearch")
    async def clansearch(
        self, ctx: commands.Context, *, extra: str | None = None
    ) -> None:
        """Launch the member search panel (no arguments allowed)."""

        if extra and extra.strip():
            await ctx.reply(
                "This one takes no arguments — just `!clansearch`.",
                mention_author=False,
            )
            return

        await self.ctrl.open_or_reuse(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecruitmentMember(bot))

