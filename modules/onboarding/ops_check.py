# modules/onboarding/ops_check.py
from __future__ import annotations

from discord.ext import commands

# ---- Guarded imports: if c1c_coreops isn't available, we no-op safely.
_COREOPS_OK = True
try:
    from c1c_coreops.rbac import tier, ops_only
    from c1c_coreops.help import help_metadata
except Exception:
    _COREOPS_OK = False

    # Soft fallbacks so importing this module never crashes startup.
    def tier(_role: str):
        def _wrap(cmd):  # passthrough decorator
            return cmd
        return _wrap

    def ops_only():
        async def _check(_ctx):
            return True
        return _check

    def help_metadata(**_kwargs):
        def _wrap(cmd):
            return cmd
        return _wrap

from modules.onboarding.schema import REQUIRED_HEADERS, load_welcome_questions
from shared.config import cfg
from shared.logging import log


class OnboardingOps(commands.Cog):
    """Operational helpers for managing the onboarding question sheet."""

    _fallback_registered: bool = False  # avoid dup standalone group

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ops_registered = False
        self._fallback_attached = False

        # Root group MUST have a (ctx) callback so discord.py can introspect.
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
        self._group.add_command(self._build_check_command())
        self._group.add_command(self._build_reload_command())

    # --------------------------- command builders ---------------------------

    def _build_check_command(self) -> commands.Command:
        cmd = commands.Command(
            self._onb_check,
            name="check",
            help="Validate the onboarding questions tab and required headers.",
            brief="Validate onboarding sheet & headers.",
        )
        tier("staff")(cmd)
        help_metadata(
            function_group="operational",
            section="onboarding",
            access_tier="staff",
            usage="!ops onb check",
        )(cmd)
        cmd.add_check(ops_only())
        cmd.cog = self
        return cmd

    def _build_reload_command(self) -> commands.Command:
        cmd = commands.Command(
            self._onb_reload,
            name="reload",
            help="Reload onboarding questions from the sheet and show a quick summary.",
            brief="Reload onboarding questions from the sheet.",
        )
        tier("staff")(cmd)
        help_metadata(
            function_group="operational",
            section="onboarding",
            access_tier="staff",
            usage="!ops onb reload",
        )(cmd)
        cmd.add_check(ops_only())
        cmd.cog = self
        return cmd

    # ------------------------------ wiring ----------------------------------

    @property
    def _usage_prefix(self) -> str:
        return "!ops onb" if self._ops_registered else "!onb"

    def configure_commands(self) -> None:
        """Attach under !ops if present, else register a standalone !onb."""
        ops_root = self.bot.get_command("ops")

        if isinstance(ops_root, commands.Group):
            # Remove standalone fallback if it exists
            if self._fallback_attached:
                removed = self.bot.remove_command(self._group.name)
                if removed is not None:
                    log.human("info", "ops wiring: removed standalone 'onb' fallback")
                self._fallback_attached = False

            if not self._ops_registered:
                ops_root.add_command(self._group)
                self._group.cog = self
                self._ops_registered = True
                log.human("info", "ops wiring: added 'onb' subgroup under ops")
        else:
            # Detach from ops if previously attached
            if self._ops_registered:
                parent = getattr(self._group, "parent", None)
                if isinstance(parent, commands.Group):
                    parent.remove_command(self._group.name)
                self._ops_registered = False

            if not self._fallback_attached:
                self.bot.add_command(self._group)
                self._group.cog = self
                self._fallback_attached = True
                log.human(
                    "warning",
                    "ops wiring: registered standalone '!onb' group as fallback",
                )

    # ------------------------------ handlers --------------------------------

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
        except Exception as exc:  # report raw for ops
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
            try:
                questions = load_welcome_questions(force_reload=True)  # if supported
            except TypeError:
                questions = load_welcome_questions()

            await ctx.reply(
                f"🔁 Reloaded onboarding questions — tab: **{tab}** • questions: **{len(questions)}**",
                mention_author=False,
            )
            log.human(
                "info",
                "🔁 Onboarding — reloaded questions",
                guild=ctx.guild.name if ctx.guild else "-",
                tab=tab,
                count=len(questions),
            )
        except Exception as exc:
            await ctx.reply(f"❌ Reload failed:\n`{exc}`", mention_author=False)
            log.human("error", "❌ Onboarding — reload error", details=str(exc))


async def setup(bot: commands.Bot) -> None:
    # If coreops isn’t importable, don’t register anything (but don’t crash).
    if not _COREOPS_OK:
        log.human(
            "warning",
            "onboarding.ops_check disabled — c1c_coreops not available",
        )
        return

    cog = OnboardingOps(bot)
    await bot.add_cog(cog)

    # Replace lingering standalone 'onb' if present to avoid dup registration
    existing_onb = bot.get_command("onb")
    if existing_onb is not None and getattr(existing_onb, "parent", None) is None:
        removed = bot.remove_command("onb")
        if removed is not None:
            log.human("info", "ops wiring: replaced lingering standalone 'onb' fallback")
        OnboardingOps._fallback_registered = False
        existing_onb = None

    # Ensure a fallback exists exactly once
    if not OnboardingOps._fallback_registered and existing_onb is None:
        bot.add_command(cog._group)
        OnboardingOps._fallback_registered = True
        cog._fallback_attached = True

    # Try to wire it under !ops if available
    cog.configure_commands()
