# Onboarding Inactivity Audit (Welcome & Promo)

## Overview
- `modules/onboarding/watcher_welcome.py`: reminder scheduling, thread classification, Discord messaging, and reminder state persistence for welcome and promo tickets.
- `modules/onboarding/sessions.py`: session model and sheet persistence fields used by the watcher and questionnaire flows.
- `shared/sheets/onboarding_sessions.py`: onboarding session sheet layout and save/load behaviour for reminder timestamps and answers.
- `shared/sheets/onboarding.py`: welcome/promo ticket row creation/upsert helpers used when threads open.

## Current behaviour (code-based)

### Job wiring
- Reminder scan scheduled via `_ensure_reminder_job`, registering a runtime scheduler job every 900s (15m) named `welcome_incomplete_scan` tagged `welcome`; invoked during cog `setup` and calls `_scan_incomplete_threads` each tick. Logger: `c1c.onboarding.welcome_watcher`.【F:modules/onboarding/watcher_welcome.py†L252-L299】【F:modules/onboarding/watcher_welcome.py†L2487-L2493】

### Ticket discovery & classification
- Welcome threads: `_scan_incomplete_threads` collects threads in the configured welcome channel using `thread_scopes.is_welcome_parent`; skips if feature flags `welcome_dialog` or `recruitment_welcome` are disabled.【F:modules/onboarding/watcher_welcome.py†L277-L299】
- Promo threads: collected from the promo channel when `promo_enabled` and `enable_promo_hook` flags are on, filtered by `thread_scopes.is_promo_parent`; only empty-ticket actions are processed.【F:modules/onboarding/watcher_welcome.py†L289-L299】【F:modules/onboarding/watcher_welcome.py†L576-L588】
- A thread is skipped if its parsed name is closed/prefix `Closed` (welcome) or unparsable; welcome parsing expects `W####` ticket codes, promo parsing expects `[RML]####-...` names.【F:modules/onboarding/watcher_welcome.py†L391-L399】【F:modules/onboarding/watcher_welcome.py†L576-L588】
- Applicant is resolved from the welcome message via `locate_welcome_message`/`extract_target_from_message`; if missing, reminders are skipped with a debug log.【F:modules/onboarding/watcher_welcome.py†L404-L409】
- Session state is loaded from the onboarding sessions sheet by `applicant_id` + `thread_id`; if none, the watcher treats the ticket as empty (no progress).【F:modules/onboarding/watcher_welcome.py†L398-L415】
- Completed or already auto-closed sessions are excluded before timing checks. Classification uses session data only (answers/step_index/completed flags) — thread content is not read.【F:modules/onboarding/watcher_welcome.py†L214-L223】【F:modules/onboarding/sessions.py†L20-L133】
- “Has progress” means any saved answers or `step_index > 0`; otherwise treated as empty.【F:modules/onboarding/watcher_welcome.py†L214-L223】
- Promo path only handles empty tickets (`reminder_empty`, `warning_empty`, `close_empty`); incomplete promo threads (answers present) exit without action.【F:modules/onboarding/watcher_welcome.py†L584-L588】

### Timing & decision logic
- Empty welcome/promo tickets: nudge at >=3h, warning at >=24h, auto-close at >=36h since thread creation, unless corresponding sheet timestamps already exist.【F:modules/onboarding/watcher_welcome.py†L214-L234】
- Incomplete welcome tickets (answers/step_index present, not completed): warning at >=24h, auto-close at >=36h. No nudge is sent because the only non-empty reminder branch requires `not has_progress`.【F:modules/onboarding/watcher_welcome.py†L235-L249】【F:modules/onboarding/watcher_welcome.py†L498-L573】
- A separate 5h `_FIRST_REMINDER_AFTER` constant is unused for non-empty paths because the `not has_progress` guard prevents it from firing once progress exists.【F:modules/onboarding/watcher_welcome.py†L214-L249】
- Auto-close triggers solely on age threshold and missing `auto_closed_at`; it does not require a prior warning timestamp.【F:modules/onboarding/watcher_welcome.py†L214-L249】

### Sheet write behaviour
- Welcome/promo ticket rows: when a ticket thread opens, `_handle_ticket_open` writes to the onboarding sheet welcome tab via `upsert_welcome` keyed by ticket number; preexisting clan/tag/closed columns are preserved if present. Keys are ticket number + username columns; not tied to applicant user IDs.【F:modules/onboarding/watcher_welcome.py†L1805-L1845】【F:shared/sheets/onboarding.py†L274-L299】
- Promo ticket creation path not observed in this file (no promo analogue of `_handle_ticket_open`).
- Onboarding session rows (welcome/promo): created/updated via `Session.save_to_sheet` using key `(user_id, thread_id)`; inserts a new row if none exists. Fields persisted: panel_message_id, step_index, answers JSON, completed flag/timestamp, reminder timestamps (`first_reminder_at`, `warning_sent_at`, `auto_closed_at`). Reminder timestamps share columns for empty vs non-empty cases (empty values overwrite).【F:modules/onboarding/sessions.py†L20-L133】【F:shared/sheets/onboarding_sessions.py†L44-L164】【F:shared/sheets/onboarding_sessions.py†L209-L227】
- Completion flows (`_persist_session_completion` in `welcome_controller`) load or create the session row and mark `completed=True`, updating answers/step_index; no separate completion row is inserted. Session start writes also use the same row key.【F:modules/onboarding/controllers/welcome_controller.py†L1236-L1299】
- Reminder handling updates the existing session row when available; if no session existed, a new session is created (with empty answers) and saved when reminders fire, potentially creating rows for threads lacking prior starts.【F:modules/onboarding/watcher_welcome.py†L411-L435】【F:modules/onboarding/watcher_welcome.py†L498-L520】

### Discord messages & thread changes
- Empty welcome: 3h nudge to user in thread asking to open questions; 24h warning to user about closure in 12h; 36h close renames thread to `Closed-{ticket}-{username}-NONE`, posts message stating questions never started and instructing recruiters to remove the user, then archives/locks the thread.【F:modules/onboarding/watcher_welcome.py†L416-L496】
- Incomplete welcome: 24h warning to user only about closure in 12h; 36h close renames to `Closed-{ticket}-{username}-NONE`, posts removal instruction to recruiters, and archives/locks.【F:modules/onboarding/watcher_welcome.py†L519-L573】
- Promo empty: 3h nudge and 24h warning to user only; 36h close renames to `Closed-{ticket}-{username}-NONE`, posts inactivity closure text without removal instruction, then archives/locks.【F:modules/onboarding/watcher_welcome.py†L576-L681】
- No Discord logging channel posts are emitted for reminders/warnings/closes; actions only message the ticket thread and use Python logging.

### Python logging
- Logger `c1c.onboarding.welcome_watcher` emits:
  - debug for skipped reminders without target user.【F:modules/onboarding/watcher_welcome.py†L404-L409】【F:modules/onboarding/watcher_welcome.py†L590-L595】
  - info for reminders/warnings/auto-close completion with thread/ticket ids.【F:modules/onboarding/watcher_welcome.py†L430-L496】【F:modules/onboarding/watcher_welcome.py†L533-L573】【F:modules/onboarding/watcher_welcome.py†L616-L681】
  - warnings on send/rename/archive failures and sheet persistence exceptions.【F:modules/onboarding/watcher_welcome.py†L422-L488】【F:modules/onboarding/watcher_welcome.py†L525-L567】【F:modules/onboarding/watcher_welcome.py†L606-L674】
- Session sheet writes log via `shared.sheets.onboarding_sessions` when rows are saved or appended; header mismatches log errors once.【F:shared/sheets/onboarding_sessions.py†L144-L164】【F:shared/sheets/onboarding_sessions.py†L192-L227】

## Spec vs Code

| Req | Status | Notes |
| --- | --- | --- |
| 0.1 | ⚠️ | Welcome ticket rows keyed by ticket number in `upsert_welcome`; session sheet rows keyed by `(user_id, thread_id)`, so multiple rows per thread are possible (e.g., reminder creating new session row when applicant_id resolves but prior start absent).【F:modules/onboarding/watcher_welcome.py†L411-L435】【F:shared/sheets/onboarding_sessions.py†L137-L164】 |
| 0.2 | ⚠️ | Completion and reminders update the session row in place when it exists, but welcome ticket logging uses a separate sheet/tab; reminder-created sessions can insert new rows if none existed earlier.【F:modules/onboarding/watcher_welcome.py†L411-L435】【F:modules/onboarding/controllers/welcome_controller.py†L1236-L1299】 |
| 0.3 | ✅ | Completion path reuses the same session row (no separate completion row).【F:modules/onboarding/controllers/welcome_controller.py†L1236-L1299】 |
| 1.4 | ✅ | `_determine_reminder_action` exits when `session.completed` is true; completed tickets are skipped for inactivity.【F:modules/onboarding/watcher_welcome.py†L214-L223】 |
| 2.5 | ⚠️ | Empty welcome defined as no progress (no answers & step_index 0). Uses session data only; if no session row, treats as empty. Promo uses same empty detection but only processes empty actions.【F:modules/onboarding/watcher_welcome.py†L214-L223】【F:modules/onboarding/watcher_welcome.py†L576-L588】 |
| 2.6 | ⚠️ | Nudge for empty welcome at 3h matches timing but message content differs; warning at 24h to user only (no recruiter mention).【F:modules/onboarding/watcher_welcome.py†L416-L456】 |
| 2.7 | ❌ | Warning does not ping recruiter; 12h-close notice only sent to user. No recruiter-targeted message.【F:modules/onboarding/watcher_welcome.py†L437-L456】 |
| 2.8 | ⚠️ | Auto-close at 36h posts removal instruction and archives, but no recruiter-only message; message is public in thread and closing logic runs even without prior warning check.【F:modules/onboarding/watcher_welcome.py†L459-L496】 |
| 3.9 | ⚠️ | Incomplete welcome defined by answers/step_index present but not completed; classification relies solely on session sheet. Promo incomplete not handled.【F:modules/onboarding/watcher_welcome.py†L214-L249】【F:modules/onboarding/watcher_welcome.py†L576-L588】 |
| 3.10 | ❌ | No 3h nudge for incomplete; first action is 24h warning.【F:modules/onboarding/watcher_welcome.py†L235-L249】【F:modules/onboarding/watcher_welcome.py†L519-L536】 |
| 3.11 | ⚠️ | 24h warning is user-only; recruiter not included.【F:modules/onboarding/watcher_welcome.py†L519-L536】 |
| 3.12 | ⚠️ | 36h auto-close posts removal instruction and archives but does not ensure prior warning; message posted in thread (not recruiter-only).【F:modules/onboarding/watcher_welcome.py†L540-L573】 |
| 4.13 | ❌ | Promo watcher only handles empty-case actions; incomplete promo tickets (answers present) are ignored for inactivity.【F:modules/onboarding/watcher_welcome.py†L584-L588】 |
| 4.14 | ✅ | Completed sessions skipped regardless of promo/welcome via shared check in `_determine_reminder_action`.【F:modules/onboarding/watcher_welcome.py†L214-L223】 |
| 4.15 | ⚠️ | Promo close message omits removal instruction as required, but timing shares empty-case schedule only; uses same rename/archival behaviour. No recruiter-specific messaging.【F:modules/onboarding/watcher_welcome.py†L645-L681】 |
| 5.16 | ⚠️ | `first_reminder_at` set on reminder or empty reminder; however empty vs non-empty share columns, so subsequent empty reminder overwrites value; not strictly “only once” per ticket variant.【F:modules/onboarding/watcher_welcome.py†L360-L379】【F:shared/sheets/onboarding_sessions.py†L209-L227】 |
| 5.17 | ⚠️ | `warning_sent_at` set on warning or empty warning with shared column, so multiple warnings overwrite. Set only when warning action succeeds.【F:modules/onboarding/watcher_welcome.py†L368-L387】【F:shared/sheets/onboarding_sessions.py†L209-L227】 |
| 5.18 | ✅ | `auto_closed_at` set when close/close_empty runs; single timestamp recorded when action executes.【F:modules/onboarding/watcher_welcome.py†L372-L387】 |
| 5.19 | ❌ | Auto-close does not require `warning_sent_at`; triggers solely on age and missing `auto_closed_at`.【F:modules/onboarding/watcher_welcome.py†L214-L249】 |
| 6.20 | ⚠️ | Reminder state persisted only after successful sends/renames; failures return early without timestamps, which keeps sheet consistent but offers no retry markers.【F:modules/onboarding/watcher_welcome.py†L422-L488】【F:modules/onboarding/watcher_welcome.py†L525-L567】 |
| 6.21 | ⚠️ | Python logs cover actions and failures; decision rationales are minimal (mostly ticket IDs). No structured reason for skips beyond missing target.【F:modules/onboarding/watcher_welcome.py†L404-L409】【F:modules/onboarding/watcher_welcome.py†L430-L496】【F:modules/onboarding/watcher_welcome.py†L533-L573】 |
| 6.22 | ❌ | No Discord logging channel posts for warnings/auto-closes/errors; all logging stays in Python logs only.【F:modules/onboarding/watcher_welcome.py†L416-L681】 |

## Key Findings
- Promo inactivity handling only covers empty tickets; incomplete promo threads are never nudged, warned, or closed for inactivity.【F:modules/onboarding/watcher_welcome.py†L584-L588】
- Welcome incomplete tickets lack a 3h nudge and warn only the user (not recruiter); auto-close proceeds after 36h regardless of prior warning state.【F:modules/onboarding/watcher_welcome.py†L235-L249】【F:modules/onboarding/watcher_welcome.py†L519-L573】
- Auto-close actions do not check `warning_sent_at`, so tickets can close at 36h even if no warning was sent (e.g., send failure).【F:modules/onboarding/watcher_welcome.py†L214-L249】【F:modules/onboarding/watcher_welcome.py†L459-L573】
- Reminder persistence can create new session rows when none exist, meaning sheet rows are not guaranteed to be created only at ticket open; welcome ticket logging uses a separate sheet keyed by ticket number, allowing multiple rows per thread across sheets.【F:modules/onboarding/watcher_welcome.py†L1805-L1845】【F:modules/onboarding/watcher_welcome.py†L411-L435】【F:shared/sheets/onboarding_sessions.py†L137-L164】
- No Discord-side logging channel messages accompany warnings or auto-closes, reducing operational visibility compared to the spec’s expectations.【F:modules/onboarding/watcher_welcome.py†L416-L681】
