# Welcome Module

## Purpose & Scope
The welcome module owns the Discord-facing experience that surrounds the onboarding engine. It listens for ticket creation signals, posts the persistent **Open questions** panel, renders onboarding prompts directly inside welcome threads, and posts recruiter-ready summaries. All user-visible embeds, buttons, role mentions, and thread renames are managed here, while the engine remains sheet-driven and Discord-agnostic.

## Responsibilities
- **Entry points** — watch Ticket Tool greetings (`"awake by reacting with"`) and 🎫 emoji reactions, then post a fresh panel with the persistent component ID `welcome.panel.open`. Startup registers the view with `timeout=None` so buttons never expire between restarts.
- **Access gates** — enforce `view_channel` (thread membership) before launching onboarding. Interactions are deferred immediately to avoid "Interaction failed" toasts.
- **Thread hygiene** — ensure welcome thread names keep their prefixes (`W####-user`, `Res-W####-user-TAG`, `Closed-W####-user-TAG`) so downstream reconciliation can parse ticket numbers.
- **Wizard UX** — host the single-message onboarding wizard (buttons, dropdowns, resume/restart actions). All edits happen in place per the lifecycle policy in `docs/ops/Onboarding.md`.
- **Embeds & panels** — format the summary embed per `docs/ops/Welcome_Summary_Spec.md`, ping recruiter roles (e.g., `<@&RecruitmentCoordinator>`), and show inline status (waiting, saved, error) so staff can see what state the recruit is in.
- **Notifications** — mention recruiter/clan roles when submissions complete, highlight gate denials in logs, and post 🧭 placement logs when tickets close and clan math runs.
- **Ticket metadata** — call onboarding sheet helpers to upsert rows in `WelcomeTickets`/`PromoTickets`, capture `clantag` selections, and rename threads when staff pick a placement.

## Non-Goals
- No question authoring, validation, or rule parsing — the module delegates to the onboarding engine and surfaces whatever it returns.
- No sheet schema changes outside welcome/placement tabs; question tabs and session tables stay under Onboarding.
- No clan availability math or reservations ledger — those routines live in Placement (`modules/placement/**`) even though welcome threads trigger them.

## Flows
### 1. Ticket Open → Panel Posted
1. Ticket Tool posts the greeting in the welcome channel. The watcher reacts 👍 and posts a new panel with the **Open questions** button (and optional **Restart** button when a session exists).
2. Panel message includes instructions (“Use the buttons below…”) and only renders once per trigger to avoid stale edits. Operators can also add 🎫 to the greeting to force a repost if Discord deleted the panel.
3. Button clicks log `panel_button_clicked` with actor, channel, thread, parent, and permission snapshots for auditing.

### 2. Launching Onboarding
1. When a recruit presses **Open questions**, the module defers the interaction, looks up the stored session (if any), and calls `modules.onboarding.welcome_flow.launch(...)` to fetch the `welcome` flow questions.
2. The wizard message renders the current question, inline summary (“So far”), and navigation buttons (Back/Next/Skip/Cancel). Text and help content come from the onboarding sheet; the welcome layer only formats them.
3. For text/number questions the watcher also listens for free-form replies in the thread so recruits who forget to press **Answer** are still captured. Valid answers update the wizard immediately; invalid input yields an inline ❌ hint.

### 3. Summary + Recruiter Handoff
1. After the last question the wizard switches to the summary card with `Finish ✅`. Pressing Finish posts the recruiter summary embed into the thread and pings configured roles.
2. Embed formatting follows `Welcome_Summary_Spec.md`: grouped sections, inline pairs (`**Power:** … • **Bracket:** …`), hide rules (`w_siege_detail` suppressed if Siege answer is "No"), and compact number formatting (K/M suffixes).
3. Once the embed is posted the wizard cleans up transient answer messages (if cleanup is enabled) and sets the session to `completed` so additional clicks display “session closed”.

### 4. Ticket Close & Placement
1. When Ticket Tool (or staff) closes/renames the thread, the watcher parses the ticket ID and posts the clan dropdown (`ClanList` cache) plus a free-text fallback.
2. Selecting a clan updates `clantag` in `WelcomeTickets`, sets `date_closed`, triggers placement math (availability recompute, reservation release/consume), and renames the thread to `Closed-W####-username-TAG` (or `-NONE`).
3. Every placement emits the 🧭 reservation log entry summarizing the action (`closed_same_clan`, `closed_other_clan`, `cancelled`) and before/after seat counts so ops can audit adjustments.
4. Manual closes without the Ticket Tool message fall back to the same helpers; the watcher reconstructs the row and still prompts for a clan if it was missing.

## Integration Points
- **Onboarding engine** — `modules/onboarding/welcome_flow` handles question loading, validation, skip logic, and persistence. Welcome passes thread/user context plus interaction handles and reacts to callbacks (validation errors, resume vs restart, completion payload).
- **Recruitment & Placement** — Placement helpers (`modules/placement/reservations.py`, `reservation_jobs.py`) reuse welcome thread parsing (`parse_welcome_thread_name`) and rely on Welcome to keep thread names consistent. Recruiters also use `!reserve`, `!onb resume`, and other CommandMatrix-listed commands inside welcome threads.
- **Watchers** — `modules/onboarding/watcher_welcome.py` binds Discord events, scheduling dedupe jobs for `WelcomeTickets`/`PromoTickets`, and notifies the runtime log channel described in `docs/ops/Logging.md`.
- **Config & toggles** — `docs/ops/Config.md` lists `WELCOME_TICKETS_TAB`, `PROMO_TICKETS_TAB`, `CLANLIST_TAB`, and feature toggles such as `WELCOME_ENABLED`, `ENABLE_WELCOME_HOOK`, and `welcome_dialog`. Welcome respects those toggles before wiring watchers at startup.

## Formatting
- **Panels:** Single message per session, edited in place. Buttons are labelled with emojis per `docs/ops/Onboarding.md` mockups (Answer ✏️, Next ➡️, Skip ⏭️, etc.). Panel content must match sheet wording; no localised rewrites.
- **Summary embed:** Layout + hide rules follow `docs/ops/Welcome_Summary_Spec.md`. Number formatting shortens `w_power`, `w_hydra_clash`, `w_chimera_clash`, `w_cvc_points`. Inline pairs use the mid-dot (`•`) separator.
- **Status messaging:** When waiting for a typed response, the panel shows “Waiting for <user>…”; resume actions show “Session restored” with the old timestamp so staff can tell whether a session was reopened or freshly started.

## Related Docs
- [`docs/ops/Module-Onboarding.md`](Module-Onboarding.md)
- [`docs/ops/WelcomeFlow.md`](WelcomeFlow.md)
- [`docs/ops/Welcome.md`](Welcome.md)
- [`docs/ops/Runbook.md`](Runbook.md)
- [`docs/ops/CommandMatrix.md`](CommandMatrix.md)
- [`docs/ops/Architecture.md`](Architecture.md)
- [`docs/ops/Welcome_Summary_Spec.md`](Welcome_Summary_Spec.md)
- [`docs/adr/ADR-0022-Module-Boundaries.md`](../adr/ADR-0022-Module-Boundaries.md)

Doc last updated: 2025-11-17 (v0.9.7)
