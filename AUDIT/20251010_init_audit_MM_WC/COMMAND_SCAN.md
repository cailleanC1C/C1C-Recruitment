# Command & Prefix Scan

## Achievements
work/Achievements/claims/middleware/coreops_prefix.py:4:from core.prefix import PREFIX_LABELS, SCOPED_PREFIXES
work/Achievements/claims/middleware/coreops_prefix.py:6:__all__ = ("format_prefix_picker",)
work/Achievements/claims/middleware/coreops_prefix.py:9:def format_prefix_picker(command_word: str) -> str:
work/Achievements/claims/middleware/coreops_prefix.py:10:    """Render guidance when someone should choose a bot-specific prefix."""
work/Achievements/claims/middleware/coreops_prefix.py:13:        f"• `{prefix} {keyword}` — {PREFIX_LABELS[prefix]}" for prefix in SCOPED_PREFIXES
work/Achievements/claims/middleware/coreops_prefix_old.py:1:# claims/middleware/coreops_prefix.py
work/Achievements/claims/middleware/coreops_prefix_old.py:2:# CoreOps prefix router & guidance for multi-bot setups.
work/Achievements/claims/middleware/coreops_prefix_old.py:7:#     and should choose a bot prefix instead.
work/Achievements/claims/middleware/coreops_prefix_old.py:41:    # Help should be prefixed for non-admins; allow via router too
work/Achievements/claims/middleware/coreops_prefix_old.py:56:def format_prefix_picker(command_word: str) -> str:
work/Achievements/claims/middleware/coreops_prefix_old.py:75:    @commands.command(name=OUR_PREFIX)
work/Achievements/claims/help.py:25:def _prefixes_str() -> str:
work/Achievements/claims/help.py:26:    """Show available CoreOps prefixes (env COREOPS_PREFIXES or defaults)."""
work/Achievements/claims/help.py:34:    """Overview help page, updated for prefix policy."""
work/Achievements/claims/help.py:42:            "**Admins** can run CoreOps with plain commands. **Everyone else** must use a **prefix**."
work/Achievements/claims/help.py:55:        name="CoreOps (admins: plain `!cmd`, others: use a prefix)",
work/Achievements/claims/help.py:57:            f"Prefixes: `{_prefixes_str()}` — e.g., `!sc health`\n"
work/Achievements/claims/help.py:64:            "• `ping` — global react-only liveness check (no prefix needed)"
work/Achievements/claims/help.py:91:    px = _prefixes_str().split(",")[0].strip() or "sc"  # sample prefix for examples
work/Achievements/claims/help.py:103:        "ping":        "`!ping` — Reacts with 🏓 to confirm liveness (global, no prefix needed).",
work/Achievements/CHANGELOG.md:22:* Updated prefix resolution to prioritize scoped prefixes (`!sc`, `!rem`, `!wc`, `!mm`) ahead of the global fallback, ensuring staff-prefixed CoreOps commands execute correctly.
work/Achievements/CHANGELOG.md:30:* CoreOps prefix router added (`!sc …`) with shared command model.
work/Achievements/REVIEW/CODEREVIEW_20251005/TYPECHECK_REPORT.md:8:- **Summary:** mypy aborted because `core/prefix.py` is discovered twice (`prefix` and `core.prefix`). Consider adding an `__init__.py`, adjusting `MYPYPATH`, or running with `--explicit-package-bases`.
work/Achievements/REVIEW/CODEREVIEW_20251005/ARCH_MAP.md:26:- **Prefix/CoreOps parity:** Share prefix guard + command registration utilities with Reminder bot (common package) to avoid drift.
work/Achievements/REVIEW/CODEREVIEW_20251005/REVIEW.md:20:- `mypy .` — ❌ (module name collision for `core/prefix.py`; see `REVIEW/TYPECHECK_REPORT.md`).【53a2f6†L1-L5】
work/Achievements/REVIEW/CODEREVIEW_20251005/TESTPLAN.md:6:| Prefix guard parity | As non-staff, run `!health` → expect prefix picker; run `!sc health` → expect denial (staff only). As staff, `!health` succeeds. | Non-staff receive picker text; staff get embed |
work/Achievements/REVIEW/CODEREVIEW_20251005/THREATS.md:15:2. **Privilege escalation**: Non-staff invoking CoreOps commands without prefix guard or role checks.
work/Achievements/cogs/ops.py:10:from core.prefix import SCOPED_PREFIXES, get_prefix
work/Achievements/cogs/ops.py:23:# ⬇️ NEW: prefix guidance helper
work/Achievements/cogs/ops.py:24:from claims.middleware.coreops_prefix import format_prefix_picker
work/Achievements/cogs/ops.py:36:      - If non-staff using a scoped prefix (e.g. !sc): (False, "Staff only.")
work/Achievements/cogs/ops.py:37:      - If non-staff without a scoped prefix: (False, picker_text)
work/Achievements/cogs/ops.py:42:    prefix = (ctx.prefix or "").strip().lower()
work/Achievements/cogs/ops.py:43:    if prefix in SCOPED_PREFIX_SET:
work/Achievements/cogs/ops.py:47:    return False, format_prefix_picker(cmd_name)
work/Achievements/cogs/ops.py:58:    # ---------------- core ops commands (staff-only; non-staff get prefix picker) ----------------
work/Achievements/cogs/ops.py:59:    @commands.command(name="health")
work/Achievements/cogs/ops.py:110:    @commands.command(name="digest")
work/Achievements/cogs/ops.py:165:    @commands.command(name="reload")
work/Achievements/cogs/ops.py:189:    @commands.command(name="checksheet")
work/Achievements/cogs/ops.py:239:    @commands.command(name="env")
work/Achievements/cogs/ops.py:258:    @commands.command(name="reboot", aliases=["restart", "rb"])
work/Achievements/cogs/ops.py:305:    bot.command_prefix = get_prefix
work/Achievements/cogs/shards/cog.py:346:    @commands.command(name="ocr")
work/Achievements/cogs/shards/cog.py:385:    @commands.command(name="shards")
work/Achievements/cogs/shards/cog.py:453:    @commands.command(name="mercy")
work/Achievements/README.md:21:* **Shared OpsCommands** introduced: all bots now use scoped prefixes for health, digest, reload, etc.
work/Achievements/README.md:42:All bots share the same admin commands (`health`, `digest`, `reload`, etc.), but each listens only to its own prefix:
work/Achievements/docs/DEVELOPMENT.md:17:  * `middleware/coreops_prefix.py` (prefix router: handles `!sc …` and bare-command picker)
work/Achievements/docs/DEVELOPMENT.md:26:* Bare CoreOps commands prompt for a **scoped prefix**; `!ping` stays **global** and **react-only**.
work/Achievements/docs/DEVELOPMENT.md:35:| `!sc health`     | Admins   | `cogs/ops.py`                         | `OpsCog.health`     | `@commands.command(name="health")`     |
work/Achievements/docs/DEVELOPMENT.md:36:| `!sc digest`     | Admins   | `cogs/ops.py`                         | `OpsCog.digest`     | `@commands.command(name="digest")`     |
work/Achievements/docs/DEVELOPMENT.md:37:| `!sc reload`     | Admins   | `cogs/ops.py`                         | `OpsCog.reload`     | `@commands.command(name="reload")`     |
work/Achievements/docs/DEVELOPMENT.md:38:| `!sc checksheet` | Admins   | `cogs/ops.py`                         | `OpsCog.checksheet` | `@commands.command(name="checksheet")` |
work/Achievements/docs/DEVELOPMENT.md:39:| `!sc env`        | Admins   | `cogs/ops.py`                         | `OpsCog.env`        | `@commands.command(name="env")`        |
work/Achievements/docs/DEVELOPMENT.md:41:| (router) `!sc …` | Everyone | `claims/middleware/coreops_prefix.py` | `CoreOpsPrefixCog`  | `class CoreOpsPrefixCog(`              |
work/Achievements/docs/DEVELOPMENT.md:103:* Preserve the CoreOps prefix behavior and bare-command picker. `!ping` stays react-only.
work/Achievements/core/prefix.py:17:def get_prefix(_bot: Any, message: Any) -> Sequence[str]:
work/Achievements/core/prefix.py:18:    """Return the runtime prefix list for discord.py."""
work/Achievements/core/prefix.py:21:    matched_prefixes: List[str] = [
work/Achievements/core/prefix.py:22:        prefix for prefix in SCOPED_PREFIXES if content.startswith(prefix)
work/Achievements/core/prefix.py:24:    remaining_prefixes: List[str] = [
work/Achievements/core/prefix.py:25:        prefix for prefix in SCOPED_PREFIXES if prefix not in matched_prefixes
work/Achievements/core/prefix.py:28:    return [*matched_prefixes, *remaining_prefixes, GLOBAL_PREFIX]
work/Achievements/core/prefix.py:31:def is_scoped_prefix(prefix: str) -> bool:
work/Achievements/core/prefix.py:32:    """Return True if the prefix is one of the scoped CoreOps prefixes."""
work/Achievements/core/prefix.py:33:    return prefix.lower() in {p.lower() for p in SCOPED_PREFIXES}
work/Achievements/c1c_claims_appreciation.py:15:from core.prefix import get_prefix
work/Achievements/c1c_claims_appreciation.py:102:bot = commands.Bot(command_prefix=get_prefix, intents=intents, strip_after_prefix=True)
work/Achievements/c1c_claims_appreciation.py:103:# Ensure prefixes like "!sc" accept a space-separated command (e.g., "!sc health").
work/Achievements/c1c_claims_appreciation.py:1467:        prefixes = await bot.get_prefix(msg)
work/Achievements/c1c_claims_appreciation.py:1468:        if isinstance(prefixes, str):
work/Achievements/c1c_claims_appreciation.py:1469:            prefixes = [prefixes]
work/Achievements/c1c_claims_appreciation.py:1472:                prefixes = list(prefixes)
work/Achievements/c1c_claims_appreciation.py:1474:                prefixes = [str(prefixes)]
work/Achievements/c1c_claims_appreciation.py:1477:        if any(content.startswith(p) for p in prefixes):
work/Achievements/c1c_claims_appreciation.py:1602:        prefix_cmds = sorted(c.name for c in bot.commands)
work/Achievements/c1c_claims_appreciation.py:1604:        log.info(f"Registered prefix commands: {prefix_cmds}")

## WelcomeCrew
work/WelcomeCrew/REVIEW/REVIEW.md:4:The current WelcomeCrew extraction ships most of the reminder-derived surface area, but two high-severity gaps block a safe carve-out. Admin/maintenance commands (`!reboot`, `!backfill`, etc.) are exposed to any member with the prefix, and several hot paths still perform blocking Google Sheets fetches directly on the Discord gateway loop when clan tags are stale or a request fails. Either issue can take the bot offline (voluntarily or via timeouts) during onboarding rushes.
work/WelcomeCrew/REVIEW/REVIEW.md:20:* **Issue:** Every prefix command (including destructive ones such as `!reboot`, `!dedupe_sheet`, `!backfill_tickets`) is callable by any user who can speak where the bot is present. Reminder’s admin role gate is missing, so a newcomer can kill the process or spam Sheets writes.
work/WelcomeCrew/REVIEW/TODOS.md:4:- [F-01] Gate all admin/maintenance prefix commands behind a `Manage Server` (or equivalent recruiter/admin role) permission check, matching Reminder.
work/WelcomeCrew/REVIEW/TESTPLAN.md:27:3. **Slash `/help` parity** — Ensure slash and prefix help both reflect current command availability.
work/WelcomeCrew/REVIEW/THREATS.md:10:1. **Privilege escalation via prefix commands (F-01).** Attackers can reboot the bot, spam Sheets writes, or dump env hints by issuing admin commands from any channel.
work/WelcomeCrew/REVIEW/FINDINGS.md:3:1. **F-01 — Prefix commands lack permission guards (High · Security).** See details in [REVIEW.md](./REVIEW.md#security--f-01-prefix-commands-lack-permission-guards).
work/WelcomeCrew/.github/issue-batches/issues.json:3:    "title": "SEC: Gate all prefix admin commands behind Manage Server",
work/WelcomeCrew/.github/issue-batches/issues.json:6:    "body": "Close privilege escalation for destructive/maintenance prefix commands.\n\n**Why**: Non-admins can trigger ops commands.\n\n**Acceptance Criteria**\n- Destructive/maintenance prefix commands (`!reboot`, `!backfill_tickets`, `!dedupe`, env/diag) fail for non-admins with a clear message; succeed for users with **Manage Server** or the designated admin role.\n- `/help` and command catalog accurately reflect gating.\n- Unit smoke: non-admin vs admin behavior verified.\n\n**Notes**\n- Align with Reminder Bot’s permission model.\n"
work/WelcomeCrew/README.md:67:All commands are prefix (`!…`). A minimal slash command `/help` is also provided.
work/WelcomeCrew/README.md:226:* Renaming is idempotent and case-normalized; it won’t double-prefix `Closed-`.
work/WelcomeCrew/docs/DOCS_MAP.md:17:- **Naming convention**: Sequential numeric prefix plus short slug (e.g., `0001-use-structure-lint.md`).
work/WelcomeCrew/docs/DOCS_MAP.md:24:- **Naming convention**: Directory per module prefixed with `MODULE_`, containing markdown/csv artifacts as needed.
work/WelcomeCrew/bot_welcomecrew.py:92:bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
work/WelcomeCrew/bot_welcomecrew.py:727:def _notify_prefix(guild: discord.Guild, closer: Optional[discord.User]) -> str:
work/WelcomeCrew/bot_welcomecrew.py:800:    prefix = _notify_prefix(thread.guild, closer)
work/WelcomeCrew/bot_welcomecrew.py:803:        f"{prefix}Need clan tag for **{username}** (ticket **{_fmt_ticket(ticket)}**) → {thread_link(thread)}"
work/WelcomeCrew/bot_welcomecrew.py:810:    (keeps a single 'Closed-' prefix; avoids double-prefixing)
work/WelcomeCrew/bot_welcomecrew.py:819:            cur_norm = "Closed-" + cur_norm[7:]  # normalize case of prefix
