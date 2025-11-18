# Recruitment Module

## Purpose & Scope
The recruitment module is the cluster-facing surface for evaluating recruits and
their fit against live clan availability. It reads the `CLANS_TAB` roster from
the recruitment sheet, renders clan search panels (`!clanmatch`, `!clansearch`),
keeps the text-only recruiter dashboard updated, and posts the Daily Recruiter
Update. Recruiters and clan leads use it to compare applications coming out of
Onboarding/Welcome, reserve seats, and trigger welcome copy for accepted
players.

## Responsibilities
- **Clan roster cache.** Maintains the `clans`, `templates`, and `clan_tags`
caches surfaced via `shared.sheets.recruitment`; CoreOps refresh jobs keep the
roster warm every 3 h while surfacing `[cache]` summaries in ops logs.
- **Search & panels.** Owns the recruiter and member search panels as well as
text-only summaries described in [`CommandMatrix.md`](CommandMatrix.md).
Feature toggles (`recruiter_panel`, `member_panel`) in `FeatureToggles`
determine which surfaces boot.
- **Emoji & welcome rendering.** Provides the crest + emoji helpers used by the
  `!welcome` command and `/emoji-pad`, pulling rows from `WelcomeTemplates`.
- **Reservation context.** Reads the `RESERVATIONS_TAB` ledger to reconcile
active holds, derive `AF/AH/AI` in `CLANS_TAB`, and feed the 🧭 placement log.
- **Reporting.** Implements the Daily Recruiter Update scheduler and the
`!report recruiters` command. Both read the `REPORTS_TAB` worksheet and log to
`LOG_CHANNEL_ID` for every post.
- **Thread tooling.** Supplies helpers used by Placement (`!reserve`) and
Welcome (thread close handlers) so that seat math and recruiter embeds use the
same adapters.

## Non-Goals
- No Discord-facing onboarding UX or ticket wizard controls (see
 [`docs/modules/Welcome.md`](Welcome.md)).
- No questionnaire parsing or onboarding sheet writes (see
 [`docs/modules/Onboarding.md`](Onboarding.md)).
- No reservation lifecycle mutations; placement helpers own `!reserve`,
reservation expiry, and the 🧭 placement log (see [`Watchers.md`](Watchers.md)).
- No scheduler orchestration or RBAC primitives; those stay inside CoreOps.

## Data Model & Sheets
### `CLANS_TAB` (`bot_info`)
- Config key: `CLANS_TAB`; defaults to `bot_info` when the Config worksheet is
missing.
- Critical columns:
  - `clan_tag` — lookup key validated against **Onboarding → ClanList (B)**.
  - `E` — human-maintained open spots; the only manual seat count.
  - `AF` — effective availability derived as `max(E − R, 0)`.
  - `AH` — active reservation count (`R`).
  - `AI` — reservation roster string (e.g., `"2 -> username1, username2"`).
  - `AG` — inactives, kept manual for ops visibility.
- Updates happen via the availability recompute helper described in
`ADR-0020-Availability-Derivation.md`: whenever reservations change, the module
writes AH/AF/AI back to the sheet and mutates the cached clan row so panels stay
correct without a global refresh.

### `RESERVATIONS_TAB` (`Reservations`)
- Config key: `RESERVATIONS_TAB`; defaults to `Reservations`.
- Ledger columns mirror the schema formalized in `ADR-0017`: `thread_id`,
`ticket_user_id`, `recruiter_id`, `clan_tag`, `clan_name`, `reserved_until`,
`created_at`, `status`, and `notes`.
- Valid `status` values: `active`, `expired`, `cancelled`, `closed_same_clan`,
`closed_other_clan`.
- Reservation-aware commands (`!reserve`, reservation buttons, auto-release
jobs) append or update rows through the shared adapter; each mutation triggers an
availability recompute for the affected clan row.

### `FeatureToggles` worksheet
- Config key: `FEATURE_TOGGLES_TAB` (default `FeatureToggles`).
- Headers: `feature_name`, `enabled`.
- Recruitment-specific toggles include `recruiter_panel`, `member_panel`,
`recruitment_welcome`, `recruitment_reports`, `placement_target_select`,
`placement_reservations`, `WELCOME_ENABLED`, `ENABLE_WELCOME_HOOK`, and
`ENABLE_PROMO_WATCHER`.
- Missing tabs or rows disable the feature and log a single admin-ping warning in
`LOG_CHANNEL_ID`.

### `WelcomeTemplates`
- Config key: `WELCOME_TEMPLATES_TAB`.
- Rows describe canned welcome posts used by `!welcome`:
  - `TAG` / `ClanTag` / `clan` — canonical clan tag lookup.
  - `TITLE`, `BODY`, `FOOTER` — embed sections (blank entries fall back to the
    `C1C` or `DEFAULT` row).
  - `TARGET_CHANNEL_ID` — optional override channel; missing/invalid IDs cause
    a guard-rail error and stay in the invoking channel.
  - `CREST_URL`, `PING_USER`, `ACTIVE`, `CLAN`, `CLANLEAD`, `DEPUTIES`,
    `GENERAL_NOTICE`, `NOTES` — fields mirrored directly into the message body.
- The troubleshooting guidance in [`Troubleshooting.md`](Troubleshooting.md)
assumes `ACTIVE = Y` for live templates; inactive rows prompt an actionable
error in Discord.

### `REPORTS_TAB` (default `Statistics`)
- Headers documented in `EPIC_DailyRecruiterUpdate.md`: `H1_Headline`,
`H2_Headline`, `Key`, `open spots`, `inactives`, `reserved spots`.
- Rows are grouped under `General Overview` and `Per Bracket` sections with
sub-headers like `Elite End Game`, `Mid Game`, and `Beginners`.
- The scheduler and manual command emit one embed per run and log `[report]
recruiters … result=ok|fail` to the runtime log channel.

## Flows
### Intake → Review → Placement
1. **Onboarding** stores validated questionnaire answers plus the recruit’s clan
preferences in Sheets and posts the recruiter-ready summary embed inside the
welcome thread.
2. **Welcome** tickets remain the primary interaction channel: recruiters review
the summary, invoke `!clanmatch` or `!clansearch`, and optionally run `!welcome`
after the clan lead confirms.
3. **Placement** consumes the same adapters to reserve or free seats when a
thread closes; ticket closures replay availability recompute helpers so `E` +
ledger stays synchronized and the 🧭 placement log captures before/after values
for `E`, `AF`, `AH`, and `AI`.

### Recruiter & member search surfaces
- `!clanmatch` (recruiter view) and `!clansearch` (member view) both render as
two persistent messages inside the recruiter thread: one for filters, one for
results. When filters change, the module edits both messages in-place. Results
cards page when multiple rows exist; empty searches replace the results embed
with a neutral “No matching clans found” message instead of spamming follow-ups.
- Ephemeral responses are reserved strictly for guard rails (permission errors,
invalid filter combinations); the refresh path never sends transient “Updating…”
responses.

### Reservations lifecycle
- Recruiters run `!reserve <clan>` inside the ticket thread (gated by the
`placement_reservations` flag). The command validates the tag against
**Onboarding → ClanList (B)**, appends an `active` row to `RESERVATIONS_TAB`, and
invokes the availability recompute helper so AF/AH/AI update immediately.
- Ticket close handlers reconcile the final placement: same-clan closures delete
the reservation row without freeing additional seats, whereas cross-clan closures
release the hold and increment the previous clan’s E-derived availability.
- Scheduled jobs rebuild reservation timers, auto-release expired holds (marking
rows as `expired`), and notify recruiters via log lines when manual follow-up is
needed.

### Reporting
- The scheduled Daily Recruiter Update posts once per UTC day at the
`REPORT_DAILY_POST_TIME` cadence defined in [`Config.md`](Config.md). Manual
runs use the `!report recruiters` command. Both mention configured recruiter
roles, render the General Overview + Per Bracket sections described in the
reporting epic, and send a structured `[report] recruiters …` log entry to
`LOG_CHANNEL_ID` summarizing the actor, destination, and result.

## Dependencies & Integration
- **Onboarding module** — supplies the questionnaire data, clan lists, and flow
state that determine whether a recruit is ready for placement.
- **Welcome module** — renders the Discord UX (ticket threads, summary embeds)
that hosts recruiter interactions; the recruitment module exposes helpers for the
`!welcome` command and emoji pipeline.
- **Placement module** — owns reservation mutations, ticket-close math, and the
🧭 log; recruitment provides shared adapters and caches (`shared.sheets.recruitment`)
so placement can read the same `CLANS_TAB` rows without duplicating logic.
- **CoreOps** — schedules refresh jobs (`clans`, `templates`, `clan_tags`),
exposes health routes (`/health`, `/ready`), and wires RBAC (`ADMIN_ROLE_IDS`,
`RECRUITER_ROLE_IDS`, etc.) for the commands listed in the Command Matrix.
- **Sheets access layer** — all reads and writes flow through the async façade
(see `ADR-0014` and [`CoreOps.md`](CoreOps.md)) to avoid blocking the Discord
event loop.

## Related Docs
- [`docs/Architecture.md`](../Architecture.md)
- [`docs/Runbook.md`](../Runbook.md)
- [`docs/modules/README.md`](README.md)
- [`docs/ops/CommandMatrix.md`](CommandMatrix.md)
- [`docs/ops/Config.md`](Config.md)
- [`docs/modules/Onboarding.md`](Onboarding.md)
- [`docs/modules/Welcome.md`](Welcome.md)
- [`docs/ops/Watchers.md`](Watchers.md)
- [`docs/runbooks/WelcomePanel.md`](../runbooks/WelcomePanel.md)
- [`docs/specs/WelcomeFlow.md`](../specs/WelcomeFlow.md)
- [`docs/specs/Welcome_Summary_Spec.md`](../specs/Welcome_Summary_Spec.md)
- [`docs/adr/ADR-0020-Availability-Derivation.md`](../adr/ADR-0020-Availability-Derivation.md)
- [`docs/adr/ADR-0017-Reservations-Placement-Schema.md`](../adr/ADR-0017-Reservations-Placement-Schema.md)
- [`docs/adr/ADR-0018_DailyRecruiterUpdate.md`](../adr/ADR-0018_DailyRecruiterUpdate.md)

Doc last updated: 2025-11-17 (v0.9.7)
