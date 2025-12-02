from __future__ import annotations

from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import admin_only

from modules.recruitment.reporting.daily_recruiter_update import (
    feature_enabled,
    log_manual_result,
    post_daily_recruiter_update,
    run_full_recruiter_reports,
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
        recruiters = len(args) >= 1 and args[0].lower() == "recruiters"
        run_all = len(args) == 2 and args[1].lower() == "all" if recruiters else False

        if not recruiters:
            await ctx.reply("Usage: !report recruiters [all]", mention_author=False)
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
        manual_results = None
        try:
            if run_all:
                manual_results = await run_full_recruiter_reports(
                    self.bot, actor="manual", user_id=getattr(ctx.author, "id", None)
                )
                ok, error = manual_results.get("report", (False, "missing"))
            else:
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

        if run_all and manual_results:
            report_ok, report_error = manual_results.get("report", (False, "missing"))
            audit_ok, audit_error = manual_results.get("audit", (False, "missing"))
            tickets_ok, tickets_error = manual_results.get("open_tickets", (False, "missing"))
            summary_lines = [
                f"Recruiter report: {'ok' if report_ok else 'fail'} ({report_error})",
                f"Role/visitor audit: {'ok' if audit_ok else 'fail'} ({audit_error})",
                f"Open tickets: {'ok' if tickets_ok else 'fail'} ({tickets_error})",
            ]
            await ctx.reply("\n".join(summary_lines), mention_author=False)
            return

        if not ok:
            await ctx.reply("Failed to post report. Check log channel.", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecruitmentReporting(bot))
