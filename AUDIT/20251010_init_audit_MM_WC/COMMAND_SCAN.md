# Command & Prefix Scan

## Matchmaker
work/Matchmaker/REVIEW/ARCH_MAP.md:4:1. **Intake (prefix commands)** — `!clanmatch` / `!clansearch` create a `ClanMatchView` (discord UI view) bound to the opener. No dedicated intake module; validation handled inline.
work/Matchmaker/REVIEW/REVIEW.md:11:**Location:** `bot_clanmatch_prefix.py:123–144`, `bot_clanmatch_prefix.py:1237–1448`, `bot_clanmatch_prefix.py:1532–1557`, `bot_clanmatch_prefix.py:1942`
work/Matchmaker/REVIEW/REVIEW.md:46:**Location:** `bot_clanmatch_prefix.py:2498–2523`
work/Matchmaker/REVIEW/REVIEW.md:65:**Location:** `bot_clanmatch_prefix.py:2529–2537`
work/Matchmaker/REVIEW/HOTSPOTS.csv:2:bot_clanmatch_prefix.py,bot_clanmatch_prefix.py,ClanMatchView.search,1415,1557,18,135,"async-ui;sheet-access","Large control flow with blocking Sheets access; candidate for extraction into matcher service"
work/Matchmaker/REVIEW/HOTSPOTS.csv:3:bot_clanmatch_prefix.py,bot_clanmatch_prefix.py,build_recruiters_summary_embed,666,712,12,47,"reporting;sheets","Parses summary table manually; consider delegating to typed sheet adapter"
work/Matchmaker/REVIEW/BOOTSTRAP_GUARDRAILS/INVENTORY.md:4:- **Root files**: `README.md`, `CHANGELOG.md`, `requirements.txt`, `bot_clanmatch_prefix.py`, `welcome.py`.
work/Matchmaker/REVIEW/BOOTSTRAP_GUARDRAILS/INVENTORY.md:14:- Runtime code lives in two Python entry points at repo root: `bot_clanmatch_prefix.py` (core bot, HTTP server, schedulers) and `welcome.py` (Cog for welcome commands).
work/Matchmaker/REVIEW/BOOTSTRAP_GUARDRAILS/ACCEPTANCE_CHECKLIST.md:9:- [ ] `REVIEW/MODULE_matchmaker/` includes scope, checklist, and dependencies for `bot_clanmatch_prefix.py`.
work/Matchmaker/REVIEW/BOOTSTRAP_GUARDRAILS/MIGRATION_PLAN.md:12:1. Create `REVIEW/MODULE_matchmaker/` to cover `bot_clanmatch_prefix.py`; include checklist, surface map, and dependencies (G-01).
work/Matchmaker/REVIEW/FINDINGS.md:3:1. **F-01** — High · Robustness — Google Sheets fetches block the event loop (`bot_clanmatch_prefix.py`).
work/Matchmaker/REVIEW/FINDINGS.md:4:2. **F-02** — Medium · DX — Welcome log channel is hard-coded (`bot_clanmatch_prefix.py`).
work/Matchmaker/REVIEW/FINDINGS.md:5:3. **F-03** — Medium · Robustness — Web server startup failures are swallowed (`bot_clanmatch_prefix.py`).
work/Matchmaker/README.md:7:* `bot_clanmatch_prefix.py` — main bot (recruiter/member panels, search, profiles, health, cache, web server, daily summaries, cleanup, watchdog).
work/Matchmaker/README.md:10:> The bot uses **prefix commands** (e.g., `!clanmatch`). Intents: `message_content` must be enabled.
work/Matchmaker/README.md:149:> **Note:** `LOG_CHANNEL_ID` is currently set inline in `bot_clanmatch_prefix.py`. Consider moving it to an env var for flexibility.
work/Matchmaker/README.md:177:   bot_clanmatch_prefix.py
work/Matchmaker/README.md:200:   python bot_clanmatch_prefix.py
work/Matchmaker/README.md:215:* Use Slash Commands permission can be off; this bot is prefix-based.
work/Matchmaker/welcome.py:18:    prefix = f"[c1c-matchmaker/welcome/{level}]"
work/Matchmaker/welcome.py:19:    line = f"{prefix} {msg}"
work/Matchmaker/welcome.py:303:    @commands.command(name="welcome")
work/Matchmaker/welcome.py:407:    @commands.command(name="welcome-refresh")
work/Matchmaker/welcome.py:419:    @commands.command(name="welcome-on")
work/Matchmaker/welcome.py:428:    @commands.command(name="welcome-off")
work/Matchmaker/welcome.py:437:    @commands.command(name="welcome-status")
work/Matchmaker/bot_clanmatch_prefix.py:1:# bot_clanmatch_prefix.py
work/Matchmaker/bot_clanmatch_prefix.py:1092:bot = commands.Bot(command_prefix="!", intents=intents)
work/Matchmaker/bot_clanmatch_prefix.py:2055:async def health_prefix(ctx: commands.Context):
work/Matchmaker/bot_clanmatch_prefix.py:2241:        print("[debug] loaded prefix commands:", ", ".join(names), flush=True)

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
