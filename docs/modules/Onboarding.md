# Onboarding Module

## Purpose & Scope
The onboarding module is the generic questionnaire engine that powers welcome and any other future intake flows. It loads question metadata from the onboarding workbook (`ONBOARDING_SHEET_ID` + `ONBOARDING_TAB`), evaluates skip/navigation rules, validates user input, and persists progress so a recruit can pause and resume. Everything in this module is Discord-agnostic: controllers emit structured state, not embeds, and downstream UX layers (Welcome, promo, future surfaces) decide how to present that state.

## Responsibilities
- **Question definitions** — read the `flow, order, qid, label, type, required, maxlen, validate, help, options, visibility_rules, nav_rules, rules` columns from the configured tab and normalise them into `Question` dataclasses (`modules/onboarding/schema.py`).
- **Rules & validation** — parse `visibility_rules`/`nav_rules` for skip logic, enforce per-question validators (regex, enumerated options, min/max lengths), and emit actionable error strings (`modules/onboarding/rules`, `modules/onboarding/validation`).
- **Session state** — track `step_index`, answered questions, derived visibility, and completion status per thread/user, including multi-device resumes.
- **Persistence** — read/write the `OnboardingSessions` tab so progress survives restarts (`shared/sheets/onboarding_sessions.py`).
- **Lifecycle logging** — emit structured diagnostics (cache refresh summaries, question counts, wizard actions, summary posted events) through the shared onboarding log helpers.
- **Summary data model** — supply the normalized answer payload (keyed by question `qid`, e.g., `w_power`, `w_hydra_diff`) that downstream UX layers format into embeds (see [`docs/modules/Welcome.md`](Welcome.md) for the summary layout).

## Non-Goals
- No Discord thread creation, embeds, panels, or button wiring — Welcome owns those UX elements.
- No recruiting-specific copywriting or wording. Labels/help text are read verbatim from Sheets.
- No placement math, ticket renames, or reservation handling — those live in Welcome/Placement modules.
- No feature toggles beyond the shared config contract; module code expects `ONBOARDING_SHEET_ID` + config rows to already exist.

## Data Model & Sheets
### Question Definition Tab (`ONBOARDING_TAB`)
- **Headers:** `flow`, `order`, `qid`, `label`, `type`, `required`, `maxlen`, `validate`, `help`, `options`, `visibility_rules`, `nav_rules`, `rules` (Config doc mirrors this schema). Rows with `flow=welcome` drive the Discord welcome dialog; other flows reuse the same engine.
- **Options:** stored as comma-separated tokens; converted into `(label, value)` tuples so both dropdowns and multi-select prompts retain sheet ordering.
- **Rules:** `visibility_rules` and `nav_rules` reference other `qid` values; parser rejects unknown IDs so skip logic does not drift.

### Session Persistence (`OnboardingSessions` tab)
- **Columns:** `user_id`, `thread_id`, `panel_message_id`, `step_index`, `completed`, `completed_at`, `answers_json`, `updated_at`.
- **`answers_json`:** compact JSON storing the latest answers keyed by `qid` (`{"w_ign": "Caillean", "w_hydra_diff": ["Hard", "Brutal"]}`, etc.).
- **Usage:** restored whenever the wizard restarts; stale panel IDs trigger a fresh panel bind but keep answers and visibility.

### Ticket & Summary Mapping
- The module prepares row values for the onboarding workbook tabs consumed by welcome/placement automation:
  - **`WelcomeTickets`** (`ticket_number`, `username`, `clantag`, `date_closed`) keeps ticket metadata; onboarding helpers upsert rows so placement math can reconcile reservations later.
  - **`PromoTickets`**, `ClanList`, and other tabs reuse the same helper plumbing via `shared/sheets/onboarding.py` but live higher in the stack (watchers decide when to call them).

## Flows
1. **Startup preload** — cache scheduler registers `onboarding_questions`; `shared.cache.telemetry` refreshes it weekly or on demand (`!ops refresh onboarding_questions`). Missing headers throw `missing config key: ONBOARDING_TAB` so ops can fix the sheet.
2. **Wizard launch** — Welcome (or another UX) asks the engine for the `welcome` flow. Questions are sorted by `order` (numeric suffix + optional alpha tag) and cached per thread.
3. **Step render & answer capture**
   - Controller hydrates metadata (label, type, validators) straight from the question row.
   - `visibility_rules` determine which questions should render. `nav_rules` allow branching (skip to `w_cvc` if Siege = "yes", etc.).
   - Incoming answers are normalised (trimmed strings, canonical booleans, sorted multi-select tokens) before being stored.
   - Validation failures return sheet-authored error strings so Welcome can display consistent inline hints.
4. **Persistence & resume** — after every mutation the engine writes to `OnboardingSessions`. Re-opening the wizard loads `answers_json`, rebuilds visibility maps, and resumes at the first incomplete question.
5. **Completion** — when `step_index` exceeds the last visible question the engine marks the session `completed`, freezes answers, emits summary logs (`modules/onboarding/logs.question_stats`), and hands the normalized payload to Welcome for embed formatting. Completed sessions reject restarts; staff can use `!onb resume @user` (CommandMatrix entry) to rebind panels inside a ticket thread when Discord ate the message.

## Dependencies
- **Config:** `shared.config` + `docs/ops/Config.md` define required env keys (`ONBOARDING_SHEET_ID`, optional `ONBOARDING_CONFIG_TAB`) and sheet tab overrides.
- **Sheets access:** `shared/sheets/onboarding_questions`, `shared/sheets/onboarding_sessions`, and `shared/sheets/onboarding` supply cached question rows, persistence helpers, and tab upserts. All I/O honours service-account credentials (`GSPREAD_CREDENTIALS`/`GOOGLE_SERVICE_ACCOUNT_JSON`).
- **Caches:** `shared.cache.telemetry` + cache scheduler refresh `onboarding_questions`; modules register buckets at startup so `!ops refresh onboarding_questions` works.
- **Logging:** `modules/onboarding/logs` standardises structured events (launch, resume, summary posted, errors) and ties into the runtime log channel configured in `docs/ops/Logging.md`.
- **Tests:** `tests/onboarding/**` cover cache wiring, sheet ID enforcement, watcher placement reconciliation, and welcome dialog controllers per ADR-0022.

## Related Docs
- [`docs/modules/Welcome.md`](Welcome.md)
- [`docs/Architecture.md`](../Architecture.md)
 - [`docs/ops/Config.md`](../ops/Config.md)
 - [`docs/ops/CommandMatrix.md`](../ops/CommandMatrix.md)
- [`docs/Runbook.md`](../Runbook.md)
- [`docs/adr/ADR-0022-Module-Boundaries.md`](../adr/ADR-0022-Module-Boundaries.md)

Doc last updated: 2025-11-17 (v0.9.7)
