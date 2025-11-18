# Changelog

### v0.9.7 — 2025-11-17  
#### Documentation Restructure & Guardrail Compliance
- **Major docs cleanup:** unified global docs, ops docs, and module docs into the new SSoT layout.
- Removed legacy folders (`reference/`, `runbooks/`, `specs/`, old onboarding/welcome flow docs).
- Introduced `docs/modules/` with full module deep-dives.
- Updated all internal links to correct SSoT paths.
- README rewritten as a clean user-facing overview.
- Added docs tree audit test to block future sprawl.
- Updated footers across docs.
#### Test Suite Consolidation
- Migrated all standalone pytest configs into `pyproject.toml`.
- Normalized test placement into `/tests/{coreops,integration,recruitment,shared,...}`.
- Cleaned up stale test files referencing removed code paths.
#### Reservations & Recruitment
- Fixed missing recompute logs when closing tickets via `!reserve`.
- Enforced canonical header order for reservation sheets.
- Removed all alias fallbacks; sheet access is now strict and clean.
- Added guardrails verifying reservation thread → ledger mapping.
- Clarified coordinator vs scout functionality.
#### Onboarding/Welcome Stability
- Improved Enter-Answer detection to avoid Discord red-toast failures.
- Strengthened session recovery to avoid “bleeding state” between tickets.
- Added inline status indicators (waiting / saved / error).
- Removed deprecated fallback flows.
- Additional watcher safeguards to prevent early retirement.
- Removed the “Enter answer” button for text prompts; the wizard now instructs recruits to “Just reply in this thread with your answer.” and captures those replies automatically.
  
### v0.9.7 — 2025-11-13
- **Audit:** Documented current reservation command flow and AF/AH/AI recompute wiring (`AUDIT/20251113_reservations-availability-wiring.md`).
- **Audit:** Analyzed reservations cache behavior and header drift causing stale availability counts (`AUDIT/20251113_reservations-cache-and-active-rows.md`).
- **Audit:** Investigated why recompute stays silent after `!reserve` despite the ledger append, tracing the helper call path, logging, and column drift (`AUDIT/20251113_reservations-recompute-not-triggering.md`).

### v0.9.7 —2025-11-08
- **Fix:** Restored keep-alive/web server startup by sweeping imports from the deprecated `shared.config` path to `shared.ports.get_port`.
- **Ops:** Added canonical boot log line `web server listening • port=<n>` to confirm bind.
- **Guardrails:** New CI check blocks reintroduction of the deprecated import path.
- **Docs:** Runbook updated with expected boot line & troubleshooting; guardrails doc updated with “Forbidden Imports”.

### v0.9.7 — 2025-11-07
- CoreOps: load `modules.coreops.cmd_cfg` as an always-on extension so `!cfg` is available (admin only).

### v0.9.7 — 2025-11-05 Onboarding Config Key & Cache Validation

* Added CI-format onboarding cache diagnostics with sheet-tail redaction and config snapshot metadata before fetch.
* Normalised onboarding question record parsing to blank missing answers for downstream consumers.
* Replaced alias-based resolver with single canonical config key **`ONBOARDING_TAB`** for the onboarding questions sheet.
* Fixed preload failure caused by mismatched alias (`onboarding.questions_tab`) and missing sheet reference.
* Enforced hard-fail on missing or empty onboarding question cache, preventing modal launch with incomplete data.
* Updated cache service logs to follow CI format (bucket, trigger, actor, duration, result, count, error).
* Wired `onboarding_questions` cache to `ONBOARDING_SHEET_ID`/`ONBOARDING_TAB`, including sheet-tail + tab metadata in refresh logs and scheduler summaries.
* Removed `ONBOARDING_QUESTIONS_TAB` alias from configuration, docs, and runtime lookups; onboarding wizard now reads from the shared cache pipeline only.
* Improved watcher lifecycle logging to correctly emit `schema_load_failed` and preload diagnostics.
* Adjusted startup refresh summary to remove alias notes and align with other cache buckets.
* Prepared PR metadata rules for Codex compliance (meta-block instruction re-added).
* Removed legacy sheet ID fallbacks across onboarding, recruitment, and shared core helpers; added onboarding resolver telemetry.

## v0.9.7 — 2025-11-04 Onboarding Stability & Preload
- Fixed crash: `TypeError: Command signature requires at least 1 parameter(s)` when initializing `onb` command group.
- Added **preload** of onboarding questions on bot startup to warm cache.
- Implemented safe re-enable + user-facing error message when onboarding schema is empty.
- Added ops-level commands (`!ops onb reload`, `!ops onb check`) for staff to manually reload or verify onboarding question cache.
- Improved error-handling and logging for onboarding launch flow (`panel_posted`, `launch_resolve_failed`, etc.).
- Refactored fallback handling to remove legacy modal dependencies.
- Adjusted message editing to ensure UI state consistency after failed schema loads.

## v0.9.7 — 2025-11-03 Interaction Timing & Panel Flow
- Reworked onboarding flow to remove modal use; converted to in-thread card interactions.
- Fixed interaction-failure issue where “Enter answer now” produced Discord’s red toast.
- Added direct user-message flow for responses, validation, and summary building.
- Integrated cleanup logic to remove transient question messages only after summary posted.
- Audited and removed obsolete fallback logic tied to modals.
- Updated logging consistency and added diagnostic event `diag: welcome_flow`.

## v0.9.7 — 2025-10-29
### Added
- Humanized Discord logging templates with shared emoji map and label helpers for guilds, channels, and users.
- In-memory dedupe (default 5s window) for refresh, welcome, and permission sync summaries.
- Standardized cache, report, permission sync, and command error Discord posts via the new helpers.
- Operator guide covering logging rules, template usage, dedupe policy, and configuration toggles.

## v0.9.7 — 2025-10-28
### Added
- **Welcome Dialog groundwork (Phase 7):**
  - Shared entrypoint `start_welcome_dialog(...)` created for both automated and manual triggers.
  - **Ticket Tool trigger** (`source="ticket"`) now starts the dialog automatically on welcome/promo thread closure.
  - **🧭 emoji fallback trigger** (`source="emoji"`) added — Recruiters, Staff, or Admins can manually start the same dialog.
  - Deduplication via pinned marker and structured logging integrated.
- All related documentation (EPIC, ADR-0017, Guardrails, Reports) updated to reflect these additions.

### Planned
- Dialog modal and summary embed integration (Phase 7 PR #5, in progress).

## v0.9.6 — 2025-10-26

### Added
- Daily Recruiter Update reporting module with UTC scheduler and manual `!report recruiters` trigger, including embed rendering, Sheets parsing, and LOG channel telemetry.

### Changed
- CoreOps surfaces now list reporting env keys, verify the Reports tab via `!checksheet`, and document the manual command in help/command matrix.
- Documentation refreshed for reporting toggle, environment keys, and architecture references.

### Tests
- Added parser and command coverage for the Daily Recruiter Update utilities.
## Unreleased / Next

- Docs: Added EPIC and ADR for Phase 6 (Daily Recruiter Update v1).
- Audit: Published docs hygiene findings at `AUDIT/20251030_DOCS_CLEANUP/report.md`.

## v0.9.6 — 2025-10-26

### Documentation
- Sync documentation with live command set, feature toggles, and watcher behavior.
- Updated configuration references, module toggle notes, and operator runbooks to reflect the current runtime.
- Bumped doc footers and indices to v0.9.6 with the 2025-10-26 review date.

## v0.9.5 — 2025-10-26

### Fixed
- Guardrails: removed the legacy `shared.help` re-export shim so the CoreOps packaging audit no longer flags shim bridges.

## v0.9.5 — 2025-10-23

### Changed
- Refactor: Introduced internal `c1c_coreops` package; legacy shared CoreOps modules now deprecated shims. No behavior changes.

### Fixed
- Recruiter panel no longer overflows Discord’s 5-row limit; pagination returned to the standalone results message with explicit row placement.
- `!clanmatch` now edits a single results message in the recruiter thread without emitting ephemeral status pings.

## v0.9.5 — 2025-10-22

- Added audit reports under `AUDIT/20251022_COREOPS_AUDIT/`.
  - Inventory of `shared/*coreops*` files and their in-repo importers
  - Symbol tables for shared & packaged CoreOps
  - Proposed actions matrix (keep/migrate/remove) + patch previews (unapplied)
- No runtime changes.
- Move recruiter command registration to `cogs/recruitment_recruiter.py`.
- Remove legacy in-module registration; preserve existing UX and flags.
- Continue honoring `PANEL_THREAD_MODE`/`PANEL_FIXED_THREAD_ID` when redirecting the panel thread.
* Consolidate CoreOps to `packages/c1c-coreops`; remove legacy shared CoreOps shims.
* Remove empty `ops/` folder.
* Add `cogs/recruitment_recruiter.py` for symmetry with member cog.
* No functional changes.
- Refactor: move `recruitment/*` → `modules/recruitment/*`.
- Consolidate common/coreops/sheets to canonical modules; rewrite imports.
- Add placeholder for member panel wiring in `cogs/recruitment_member.py`.
- Document optional `MEMBER_PANEL_*` envs (not used yet).
- Record ADR-0011.

## v0.9.5 — 2025-10-21

### Phase 5 : Recruitment Module Updates

**Added**
- `!clan` command restored (public). Displays clan profile and entry criteria with crest thumbnail and 💡 reaction toggle.
- `!clanmatch` command rebuilt as text-only recruiter panel for mobile performance.
- `!rec env` now shows Feature Toggles under “Sheets / Config Keys”.
- Feature toggles introduced: `clan_profile`, `recruiter_panel`.

**Fixed**
- Recruiter panel no longer spawns outside thread or stalls on update.
- Search updates now confirm refresh instead of sending duplicates.

**Documentation**
- Updated: all command, ops, and user docs to reflect Phase 5 features.

## [v0.9.4] — 2025-10-20

### Added
- Feature toggles (Config-driven) with strict TRUE-only policy and admin-ping on misconfig.

### Changed
- Runtime loader gates user-facing recruitment modules behind toggles.

### Docs
- Integrated toggles docs into README/Architecture/Config/Runbook/Troubleshooting/CommandMatrix/Watchers; removed redundant contracts page.

## [v0.9.3-phase3b-rc6] — 2025-10-19

### Added
- ✅ `!checksheet` diagnostics (Tabs & Headers) + `--debug` preview
- ✅ `!rec refresh all` summary embed with actor, duration, and retry telemetry
- ✅ Detailed help embeds now show command usage signatures
- ✅ Preloader warm-up on startup; `bot_info` auto-refresh every 3 h
- ✅ Refreshed `!config` embed (viewer style with meta overlay)

### Changed
- ⚙️ `!config` embed viewer replaces raw IDs with guild names + meta block
- ⚙️ `!reload --reboot` documents soft reboot flag alongside config reload
- ⚙️ Removed embed timestamps; footer shows versions only

### Fixed
- 🛠 Guardrail compliance: commands use public cache/sheets APIs only
- 🛠 `refresh_now()` argument alignment (trigger → actor)
- 🛠 Cron refresh logs write success/failure summaries to the ops channel

## [v0.9.3-phase3b-rc4] — 2025-10-17
### Changed
- Unified all command prefixes under `!` and `@mention`.
- Implemented dynamic help with tier grouping (User / Staff / Admin).
- Added tier decorators to all commands (`@tier("...")`).
- Removed legacy `!reboot` (redundant with `!refresh`).
- Removed `manage_guild` bypass; full RBAC enforcement via helper functions.
- Updated help text copy (C1C community tone, cleaner usage examples).
- Gating now silent during help rendering (no "Staff only." spam).

### Fixed
- Duplicate help entries across tiers.
- Hidden admin/staff commands now visible only to allowed roles.

### Documentation
- Added “Adding New Commands” guide.
- Updated Ops Contract and command overview for Phase 3b.

## [v0.9.3-phase3b-rc3] — Phase 3b Docs Alignment - 2025-10-16

### CoreOps & Admin Ops
- Admin-only gating standardized across ops commands.
- New `!env` command: grouped, masked output with ID → name resolution.
- Embeds unified: versions in footer, no inline datetime (use message timestamp).
- `!rec refresh all` now posts a single summary embed listing all buckets with duration/result/retries.

## [v0.9.3-phase3] — Phase 3 Completion - 2025-10-16

### Sheets Access Layer + CoreOps Refresh

### Docs & versioning
- All runtime and docs bumped to v0.9.3.
- Unified runtime confirmed stable across env groups.

### Cache & Async Layer
- Async back-off and retry helpers implemented.
- Safe cancel propagation and non-blocking refresh confirmed.
- TTL defaults: clans 3 h, templates 7 d, clan_tags 7 d.
- Scheduled refresh cadence: 3 h / weekly (Mon 06:00 UTC).
- Background logging to LOG_CHANNEL_ID with actor + trigger tags.

### CoreOps Groundwork
- Refresh commands consolidated into shared CoreOps.
- Admin and Staff roles now use !rec refresh all and !rec refresh clansinfo.
- RBAC guard logic preserved; clear permission errors surfaced.
- Refresher logs record bucket, trigger, actor, duration, result, error.
- `!rec refresh all` now posts a single summary embed listing all buckets with duration/result/retries.

### Diagnostics & Health
- !health embed now displays cache ages, TTLs, and next refresh times (UTC date + time).
- Refresher telemetry captures retry counts and error text across attempts.
- Enhanced observability for manual vs scheduled triggers.
- Embeds standardized: versions moved to footer; inline date/time removed (embed timestamp used).

### Runtime Reliability
- Gspread dependency added to enable template bucket refresh.
- Ops cog removed (merged into CoreOps for clarity).
- Workflow auto-label and milestone fix verified.

## [v0.9.3-phase3-rc1] — Phase 3 rollout (Shared CoreOps refresh) - 2025-10-15

- CoreOps: unify refresh commands in shared cog; removed duplicate definitions.
- Runtime: add gspread dependency to enable templates bucket refresh.
- Cache: improved refresh failure diagnostics — both first and retry errors are logged.
- Health: 'next' now shows full UTC date + time (YYYY-MM-DD HH:MM UTC).

## [v0.9.2] — Phase 2 complete (Per-Environment Configuration) - 2025-10-15

- README is user-facing and versioned to v0.9.2.
- Stamped v0.9.2 across architecture, development, ops, ops_coreops, contracts.
- Added footer notes: "Doc last updated: 2025-10-15 (v0.9.2)".
- CoreOps: fix refresh subcommand registration; replace private cache calls with public API; relocate staff `!config` summary into CoreOps.
- Sheets access layer migration remains slated for Phase 3; CoreOps expansion for Phase 3b.

## [v0.9.2] - Phase 2 — 2025-10-14

### Added
- Unified single-bot runtime covering recruitment search, welcome, and onboarding watchers.
- Centralized per-environment configuration with shared key set and Config tab requirements.
- Guild allow-list gating at startup and consolidated logging to #bot-production.

### Changed
- CoreOps command surface harmonized to shared `!help`, `!ping`, `!health`, and `!reload` handlers.
- Watchdog defaults aligned across environments with configurable cadence, stall, and grace values.

### Deprecated
- Legacy duplicate environment keys and multi-bot deployment instructions removed from docs.

## [v0.9.1] — 2025-10-14

### Added
- CoreOps cog with commands: ping, help, health, env, digest.
- Help embed with footer: "Bot v{BOT_VERSION} • CoreOps v1.0.0 • <Vienna or UTC time>".
- Role-based RBAC: ADMIN_ROLE_IDS (list), STAFF_ROLE_IDS (list). No user-ID gating.
- Admin "bang" shortcuts: !health, !env, !digest, !help (Admin role only).
- Prefix handling: supports !rec, !rec␣, rec, rec␣ and @mention.
- Watchdog mirrored from legacy: keepalive cadence, stall, disconnect grace; connection-aware.
- Socket heartbeat with READY/connect/disconnect tracking and snapshots.
- Health server (/ready, /healthz) bootstrapped for Render.
- GitHub Actions → Render flow: "latest-wins" lane wait/cancel script.

### Changed
- Prefix parsing fix to accept with/without space variants.
- Intents: enabled members intent to support role-aware gating.

### Fixed
- Command registration conflict with discord.py default help (removed default help).
- Help footer timezone fallback (Vienna → UTC if tzdata missing).

## 2025-10-14 — Phase 2: Per-Environment Configuration
- Unified single-bot scaffold with modules imported.
- Centralized env config with `ENV_NAME` and `GUILD_IDS` allow-list.
- One runtime: watchdog, scheduler, health server.
- Logs routed to `LOG_CHANNEL_ID` (#bot-production).
- Final env names standardized; legacy singular admin key deprecated.
- Sheet tab names moved out of env into each Sheet's **Config** tab.

---
Doc last updated: 2025-11-08 (v0.9.7)
