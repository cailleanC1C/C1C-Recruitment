from __future__ import annotations

from discord.ext import commands

from modules.onboarding.schema import REQUIRED_HEADERS, load_welcome_questions
from shared.config import cfg
from shared.logs import log


class OnboardingCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ops_registered = False
        self._fallback_registered = False

        # Provide an explicit callback so discord.py can introspect the command
        # signature when registering the group. Without a callable here the
        # extension raises "Command signature requires at least 1 parameter(s)"
        # during load.
        self._group = commands.Group(
            callback=self._onb_root,
            name="onb",
            invoke_without_command=True,
            help="Operational helpers for onboarding questions.",
            brief="Operational helpers for onboarding questions.",
        )
        self._group.cog = self
        tier("staff")(self._group)
        extras = getattr(self._group, "extras", None)
        if not isinstance(extras, dict):
            extras = {}
            self._group.extras = extras
        extras.setdefault("function_group", "operational")
        extras.setdefault("help_section", "onboarding")
        extras.setdefault("access_tier", "staff")
        extras.setdefault("help_usage", "!ops onb <command>")

        self._check_command = self._build_check_command()
        self._reload_command = self._build_reload_command()

        self._group.add_command(self._check_command)
        self._group.add_command(self._reload_command)

    # ------------------------------------------------------------------
    # Command builders
    def _build_check_command(self) -> commands.Command:
        command = commands.Command(
            self._onb_check,
            name="check",
            help="Validate the onboarding questions tab and required headers.",
            brief="Validate onboarding sheet & headers.",
        )
        tier("staff")(command)
        help_metadata(
            function_group="operational",
            section="onboarding",
            access_tier="staff",
            usage="!ops onb check",
        )(command)
        command.add_check(ops_only())
        command.cog = self
        return command

    def _build_reload_command(self) -> commands.Command:
        command = commands.Command(
            self._onb_reload,
            name="reload",
            help="Reload onboarding questions from the sheet and show a quick summary.",
            brief="Reload onboarding questions from the sheet.",
        )
        tier("staff")(command)
        help_metadata(
            function_group="operational",
            section="onboarding",
            access_tier="staff",
            usage="!ops onb reload",
        )(command)
        command.add_check(ops_only())
        command.cog = self
        return command

    # ------------------------------------------------------------------
    # Shared helpers
    @property
    def _usage_prefix(self) -> str:
        return "!ops onb" if self._ops_registered else "!onb"

    def configure_commands(self) -> None:
        self._attach_group()

    def _attach_group(self) -> None:
        ops_root = self.bot.get_command("ops")

    @commands.command(name="onb:check")
    @commands.has_permissions(administrator=True)
    async def onb_check(self, ctx: commands.Context):
        """Validate the onboarding questions tab (sheet-only, strict)."""

        try:
            tab = cfg.get("onboarding.questions_tab") or "<unset>"
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


async def setup(bot: commands.Bot) -> None:
    cog = OnboardingOps(bot)
    await bot.add_cog(cog)
    try:
        bot.add_command(cog._group)
    except Exception:
        # The command may already exist (e.g. hot reload); ignore safely.
        pass
    cog.configure_commands()
