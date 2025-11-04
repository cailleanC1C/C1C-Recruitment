from __future__ import annotations

from discord.ext import commands

from modules.onboarding.schema import REQUIRED_HEADERS, load_welcome_questions
from shared.config import get_onboarding_questions_tab
from modules.common.logs import log


class OnboardingCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="onb:check")
    @commands.has_permissions(administrator=True)
    async def onb_check(self, ctx: commands.Context):
        """Validate the onboarding questions tab (sheet-only, strict)."""

        try:
            tab = get_onboarding_questions_tab() or "<unset>"
            questions = load_welcome_questions()
            await ctx.reply(
                "✅ Onboarding sheet OK — tab: **{}** • questions: **{}** • headers OK: {}".format(
                    tab, len(questions), ", ".join(sorted(REQUIRED_HEADERS))
                ),
                mention_author=False,
            )
            log.human(
                "info",
                "✅ Onboarding — schema ok",
                guild=ctx.guild.name if ctx.guild else "-",
                tab=tab,
                count=len(questions),
            )
        except Exception as exc:  # noqa: BLE001 - report raw error to staff
            await ctx.reply(
                "❌ Onboarding sheet invalid:\n`{}`\nFix the sheet or config and try again.".format(
                    exc
                ),
                mention_author=False,
            )
            log.human("error", "❌ Onboarding — schema error", details=str(exc))


async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingCheck(bot))
