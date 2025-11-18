# Placement Module

## Purpose & Scope
Placement enforces the rules that determine where a recruit lands once a welcome thread is ready to close. The module:
- Maintains the reservations ledger so recruiters can hold and release seats directly from Discord threads.
- Reconciles manual capacity, reservations, and ticket metadata before Welcome renames the thread and posts the 🧭 placement log.
- Owns the scheduled jobs that remind staff about expiring holds and auto-release stale reservations so the clans tab stays accurate.

## Responsibilities
- **Interactive reservations.** `!reserve` runs inside welcome tickets, walks recruiters through picking the recruit, expiration date, and justification, writes the row to the `Reservations` tab, and immediately recomputes clan availability so AF/AH/AI reflect the hold. The command also renames the thread to `Res-W####-user-TAG` to signal the reservation in-channel. 【F:modules/placement/reservations.py†L656-L915】
- **Release, extend, and audit.** The same cog exposes `!reserve release …`, `!reserve extend …`, and `!reservations` so staff (and whitelisted clan leads) can inspect ledger rows from either the ticket thread or the recruiter control thread/interact channel. Each path updates the sheet (status, expiry) and re-runs `adjust_manual_open_spots`/`recompute_clan_availability` for the affected tag. 【F:modules/placement/reservations.py†L942-L1320】
- **Ticket-close reconciliation.** When Welcome marks a recruit as placed, the watcher updates any linked reservation rows, applies the delta to manual open spots, recomputes availability, renames the thread to the final `Closed-W####-user-TAG` format, and posts the placement summary with before/after clan math snapshots. 【F:modules/onboarding/watcher_welcome.py†L1479-L1549】
- **Daily upkeep.** `reservations_reminder_daily` and `reservations_autorelease_daily` run at 12:00Z and 18:00Z respectively to ping recruiters inside ticket threads about same-day expirations, summarize overdue holds in the recruiter control thread, mark ledger rows as `expired`, and recompute availability for each touched clan. These jobs are guarded by the same `feature_reservations` toggles as the commands. 【F:modules/placement/reservation_jobs.py†L23-L260】
- **Target-selection stub.** `modules/placement/target_select.py` currently only logs when it loads. The stub reserves the namespace for future automation but intentionally exposes no commands today. 【F:modules/placement/target_select.py†L1-L12】

## Non-Goals
- No onboarding question or session logic; those responsibilities stay inside the onboarding engine. 【F:docs/modules/Onboarding.md†L3-L45】
- No Discord UX elements (panels, embeds, ticket lifecycle prompts); Welcome owns the user-facing surface and simply calls Placement helpers. 【F:docs/modules/Welcome.md†L3-L45】
- No standalone reservations schema definitions — the Config doc remains the source of truth for environment keys, FeatureToggles rows, and tab overrides. 【F:docs/ops/Config.md†L76-L223】

## Data Model & Sheets
### Reservations ledger (`Reservations` tab)
- **Headers:** `thread_id`, `ticket_user_id`, `recruiter_id`, `clan_tag`, `reserved_until`, `created_at`, `status`, `notes`, `username_snapshot`. Every append or update goes through `shared.sheets.reservations` so the schema is validated before writes. 【F:shared/sheets/reservations.py†L28-L120】
- **Status management:** Rows start as `active`. Ticket-close reconciliation, manual releases, or the auto-release job flip `status` to `released`/`expired` via `update_reservation_status`, while `update_reservation_expiry` adjusts `reserved_until` for extensions. 【F:shared/sheets/reservations.py†L188-L282】

### Clans roster (`CLANS` tab)
- **Manual open spots:** `adjust_manual_open_spots` edits the header resolved for `open_spots` (defaults to the AF column) so manual seat adjustments always persist in the worksheet and cache. 【F:modules/recruitment/availability.py†L16-L52】
- **Derived availability:** `recompute_clan_availability` reads the `Reservations` tab, counts active holds, and rewrites `AF{row}:AI{row}` with `available_after_reservations`, the existing `AG` value, `reservation_count`, and a `reservation_summary` that lists holder names for quick audits. 【F:modules/recruitment/availability.py†L54-L118】

### Welcome ticket metadata (`WelcomeTickets` tab)
- The onboarding helpers keep `ticket_number`, `username`, `clantag`, and `date_closed` in sync so Placement can always resolve the right row when a ticket closes. 【F:docs/modules/Onboarding.md†L31-L35】

## Flows
1. **Ticket ready for placement.** Welcome parses the thread name, applies any pending reservation deltas (consume, release, or convert holds), and writes the final `clantag` plus before/after math snapshots before renaming the thread and logging the result. 【F:modules/onboarding/watcher_welcome.py†L1479-L1549】
2. **Evaluating options.** Recruiters can inspect availability and existing holds via `!reservations` in the control/interact channels before deciding on a clan. Clan leads only gain read access in the interact channel; recruiters retain write authority everywhere. 【F:modules/placement/reservations.py†L1268-L1320】
3. **Recording the decision.** Placing a recruit or creating a hold updates the ledger, recomputes the `CLANS` row, and posts thread-level confirmations plus 🧭 logs so Ops can audit the action later. Reminder and auto-release jobs ensure stale reservations never block AF/AH/AI for long. 【F:modules/placement/reservations.py†L656-L915】【F:modules/placement/reservation_jobs.py†L38-L260】

## Dependencies & Integration
- **Recruitment module.** Placement imports the availability helpers to adjust manual capacity and recompute `CLANS` rows after every reservation, release, or placement. 【F:modules/placement/reservations.py†L17-L24】【F:modules/recruitment/availability.py†L16-L118】
- **Welcome module.** Watchers provide context (ticket IDs, usernames, reserved tags) and call Placement helpers during thread renames; Placement in turn uses Welcome utilities such as `parse_welcome_thread_name`/`rename_thread_to_reserved`. 【F:modules/placement/reservations.py†L17-L29】【F:modules/onboarding/watcher_welcome.py†L1479-L1549】
- **CoreOps runtime.** The scheduler registers the reminder and auto-release loops via `runtime.scheduler.spawn`, and feature toggles (`FEATURE_RESERVATIONS`, `placement_reservations`) guard both the commands and cron jobs. 【F:modules/placement/reservation_jobs.py†L23-L307】
- **Shared config.** Role/channel helpers (`get_clan_lead_ids`, `get_recruiters_thread_id`, `get_recruitment_interact_channel_id`, `get_welcome_channel_id`) decide who can run the commands and where summaries post. 【F:modules/placement/reservations.py†L17-L33】

## Related Docs
- [`docs/Architecture.md`](../Architecture.md)
- [`docs/Runbook.md`](../Runbook.md)
- [`docs/README.md`](../README.md)
- [`docs/modules/Recruitment.md`](Recruitment.md)
- [`docs/ops/CommandMatrix.md`](CommandMatrix.md)
- [`docs/ops/Config.md`](Config.md)
- [`docs/modules/Onboarding.md`](Onboarding.md)
- [`docs/modules/Welcome.md`](Welcome.md)
- [`docs/adr/ADR-0017-Reservations-Placement-Schema.md`](../adr/ADR-0017-Reservations-Placement-Schema.md)
- [`docs/adr/ADR-0019-Introduction-of-Clan-SeatReservations.md`](../adr/ADR-0019-Introduction-of-Clan-SeatReservations.md)
- [`docs/adr/ADR-0021-availability-recompute-helper.md`](../adr/ADR-0021-availability-recompute-helper.md)

Doc last updated: 2025-11-17 (v0.9.7)
