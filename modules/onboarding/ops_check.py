# modules/onboarding/ops_check.py
from __future__ import annotations

from discord.ext import commands

from c1c_coreops.rbac import tier, ops_only
from c1c_coreops.help import help_metadata

from modules.onboarding.schema import REQUIRED_HEADERS, load_welcome_questions
from shared.config import cfg
from shared.logging import log


class OnboardingOps(commands.Cog):
    """Operational helpers for managing the onboarding question sheet."""

    # Guard so hot-reloads / second paths don't re-register the same group
    _fallback_registered: bool = False

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ops_registered = False
        self._fallback_attached = False

        # Root group needs a callable with (ctx) so discord.py can introspect.
        self._group = commands.Group(
            callback=self._onb_root,
            name="onb",
            invoke_without_command=True,
            help="Operational helpers for onboarding questions.",
            brief="Operational helpers for onboarding questions.",
        )
        self._group.cog = self

        # RBAC + help metadata for the group
        tier("staff")(self._group)
        extras = getattr(self._group, "extras", None)
        if not isinstance(extras, dict):
            extras = {}
            self._group.extras = extras
        extras.setdefault("function_group", "operational")
        extras.setdefault("help_section", "onboarding")
        extras.setdefault("access_tier", "staff")
        extras.setdefault("help_usage", "!ops onb <command>")

        # Subcommands
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
        """Attach under !ops if present, otherwise expose a standalone !onb."""
        ops_root = self.bot.get_command("ops")

        if isinstance(ops_root, commands.Group):
            # Remove any lingering standalone registration
            if self._fallback_attached:
                removed = self.bot.remove_command(self._group.name)
                if removed is not None:
                    log.human("info", "ops wiring: removed standalone 'onb' fallback")
                self._fallback_attached = False

            # Attach as subgroup under ops
            if not self._ops_registered:
                ops_root.add_command(self._group)
                self._group.cog = self
                self._ops_registered = True
                log.human("info", "ops wiring: added 'onb' subgroup under ops")
        else:
            # Detach from ops if it was previously attached
            if self._ops_registered:
                parent = getattr(self._group, "parent", None)
                if isinstance(parent, commands.Group):
                    parent.remove_command(self._group.name)
                self._ops_registered = False

            # Register standalone fallback
            if not self._fallback_attached:
                self.bot.add_command(self._group)
                self._group.cog = self
                self._fallback_attached = True
                log.human(
                    "warning",
                    "ops wiring: registered standalone '!onb' group as fallback",
                )

    # ------------------------------------------------------------------
    # Handlers
    async def _onb_root(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        await ctx.reply(
            f"Usage: `{self._usage_prefix} reload` or `{self._usage_prefix} check`",
            mention_author=False,
        )

    async def _onb_check(self, ctx: commands.Context) -> None:
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

    async def _onb_reload(self, ctx: commands.Context) -> None:
        """Force reload of onboarding questions and show a brief summary."""
        try:
            tab = cfg.get("onboarding.questions_tab") or "<unset>"
            questions = load_welcome_questions(force_reload=True)  # if supported; else ignore kw
            count = len(questions)
            await ctx.reply(
                f"🔁 Reloaded onboarding questions — tab: **{tab}** • questions: **{count}**",
                mention_author=False,
            )
            log.human(
                "info",
                "🔁 Onboarding — reloaded questions",
                guild=ctx.guild.name if ctx.guild else "-",
                tab=tab,
                count=count,
            )
        except TypeError:
            # Fallback if load_welcome_questions doesn't support force_reload
            try:
                tab = cfg.get("onboarding.questions_tab") or "<unset>"
                questions = load_welcome_questions()
                count = len(questions)
                await ctx.reply(
                    f"🔁 Reloaded onboarding questions — tab: **{tab}** • questions: **{count}**",
                    mention_author=False,
                )
                log.human(
                    "info",
                    "🔁 Onboarding — reloaded questions (no force flag)",
                    guild=ctx.guild.name if ctx.guild else "-",
                    tab=tab,
                    count=count,
                )
            except Exception as exc:  # noqa: BLE001
                await ctx.reply(
                    "❌ Reload failed:\n`{}`".format(exc),
                    mention_author=False,
                )
                log.human("error", "❌ Onboarding — reload error", details=str(exc))
        except Exception as exc:  # noqa: BLE001
            await ctx.reply(
                "❌ Reload failed:\n`{}`".format(exc),
                mention_author=False,
            )
            log.human("error", "❌ Onboarding — reload error", details=str(exc))


async def setup(bot: commands.Bot) -> None:
    cog = OnboardingOps(bot)
    await bot.add_cog(cog)

    # Replace lingering standalone 'onb' if present to avoid dup registration
    existing_onb = bot.get_command("onb")
    if existing_onb is not None and getattr(existing_onb, "parent", None) is None:
        removed = bot.remove_command("onb")
        if removed is not None:
            log.human("info", "ops wiring: replaced lingering standalone 'onb' fallback")
        existing_onb = None
        OnboardingOps._fallback_registered = False

    # Ensure a fallback exists exactly once
    if not OnboardingOps._fallback_registered and existing_onb is None:
        bot.add_command(cog._group)
        OnboardingOps._fallback_registered = True
        cog._fallback_attached = True

    # Try to wire it under !ops if available
    cog.configure_commands()
