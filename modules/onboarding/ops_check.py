from __future__ import annotations

import discord
from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import ops_only
from modules.common.logs import log
from modules.onboarding.schema import REQUIRED_HEADERS, load_welcome_questions
from shared.config import get_onboarding_questions_tab
from shared.sheets import onboarding_questions


class OnboardingOps(commands.Cog):
    """Operational helpers for managing the onboarding question sheet."""

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

        if isinstance(ops_root, commands.Group):
            if self._fallback_registered:
                removed = self.bot.remove_command(self._group.name)
                if removed is not None:
                    log.human(
                        "info",
                        "ops wiring: removed standalone 'onb' fallback",
                    )
                self._fallback_registered = False
            if not self._ops_registered:
                ops_root.add_command(self._group)
                self._group.cog = self
                self._ops_registered = True
                log.human("info", "ops wiring: added 'onb' subgroup under ops")
        else:
            if self._ops_registered:
                parent = getattr(self._group, "parent", None)
                if isinstance(parent, commands.Group):
                    parent.remove_command(self._group.name)
                self._ops_registered = False
            if not self._fallback_registered:
                self.bot.add_command(self._group)
                self._group.cog = self
                self._fallback_registered = True
                log.human(
                    "warning",
                    "ops wiring: registered standalone '!onb' group as fallback",
                )

    async def _onb_root(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        await ctx.reply(
            f"Usage: `{self._usage_prefix} reload` or `{self._usage_prefix} check`",
            mention_author=False,
        )

    async def _onb_check(self, ctx: commands.Context) -> None:
        """Validate the onboarding questions tab (sheet-only, strict)."""

        tab = get_onboarding_questions_tab() or "<unset>"
        try:
            questions = load_welcome_questions()
        except Exception as exc:  # noqa: BLE001 - report raw error to staff
            await ctx.reply(
                "❌ Onboarding sheet invalid:\n`{}`\nFix the sheet or config and try again.".format(
                    exc
                ),
                mention_author=False,
            )
            log.human("error", "❌ Onboarding — schema error", details=str(exc))
            return

        headers_line = ", ".join(sorted(REQUIRED_HEADERS))
        await ctx.reply(
            "✅ Onboarding sheet OK — tab: **{}** • questions: **{}** • headers OK: {}".format(
                tab, len(questions), headers_line
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

    async def _onb_reload(self, ctx: commands.Context) -> None:
        """Reload onboarding questions from the sheet and show a quick summary."""

        try:
            await ctx.trigger_typing()
        except Exception:
            pass

        try:
            onboarding_questions.invalidate_cache()
            questions = onboarding_questions.get_questions("welcome")
        except Exception as exc:  # noqa: BLE001 - show raw error to staff
            await ctx.reply(
                "❌ Failed to reload onboarding questions:\n`{}`".format(exc),
                mention_author=False,
            )
            log.human("error", "❌ Onboarding — reload failed", details=str(exc))
            return

        count = len(questions)
        sample_qids = [question.qid for question in questions[:5] if question.qid]

        if count == 0:
            description = (
                "❌ Reloaded: **0** questions for `flow=welcome`.\n"
                "Use `!ops onb check` for header details."
            )
            colour = 0xCC3333
        else:
            sample_line = ""
            if sample_qids:
                sample_line = f"\nSample qids: `{', '.join(sample_qids)}`"
            description = (
                f"✅ Reloaded: **{count}** questions for `flow=welcome`."
                f"{sample_line}"
            )
            colour = 0x33AA55

        embed = discord.Embed(description=description, colour=colour)
        try:
            await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            await ctx.reply(description, mention_author=False)

        log.human(
            "info",
            "✅ Onboarding — reload complete",
            guild=ctx.guild.name if ctx.guild else "-",
            count=count,
            sample=sample_qids,
        )

    # ------------------------------------------------------------------
    # Event hooks
    @commands.Cog.listener()
    async def on_cog_add(self, _cog: commands.Cog) -> None:
        self._attach_group()

    @commands.Cog.listener()
    async def on_cog_remove(self, _cog: commands.Cog) -> None:
        self._attach_group()


async def setup(bot: commands.Bot) -> None:
    cog = OnboardingOps(bot)
    await bot.add_cog(cog)
    try:
        bot.add_command(cog._group)
    except Exception:
        # The command may already exist (e.g. hot reload); ignore safely.
        pass
    cog.configure_commands()
