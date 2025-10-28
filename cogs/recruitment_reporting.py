from __future__ import annotations

from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import admin_only

from modules.recruitment.reporting.daily_recruiter_update import (
    feature_enabled,
    log_manual_result,
    post_daily_recruiter_update,
)


class RecruitmentReporting(commands.Cog):
    """Admin commands for recruitment reporting."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.command(
        name="report",
        help="Posts the Daily Recruiter Update to the configured channel immediately.",
        brief="Posts the Daily Recruiter Update immediately.",
    )
    @admin_only()
    async def report_group(self, ctx: commands.Context, *args: str) -> None:
        if len(args) != 1 or args[0].lower() != "recruiters":
            await ctx.reply("Usage: !report recruiters", mention_author=False)
            return

        if not feature_enabled():
            await ctx.reply("Daily Recruiter Update is disabled.", mention_author=False)
            await log_manual_result(
                bot=self.bot,
                user_id=getattr(ctx.author, "id", 0),
                result="blocked",
                error="feature-off",
            )
            return

        ok: bool
        error: str
        try:
            ok, error = await post_daily_recruiter_update(self.bot)
        except Exception as exc:  # pragma: no cover - defensive guard
            ok = False
            error = f"{type(exc).__name__}:{exc}"

        result = "ok" if ok else "fail"
        await log_manual_result(
            bot=self.bot,
            user_id=getattr(ctx.author, "id", 0),
            result=result,
            error=error,
        )

        if not ok:
            await ctx.reply("Failed to post report. Check log channel.", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecruitmentReporting(bot))
