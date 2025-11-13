# 📄 ADR-0019 — Introduction of Clan Seat Reservations

## **Context**
Recruiters need a reliable, auditable mechanism to temporarily hold a seat in a clan for a recruit during onboarding and placement.
Previously, availability was manually edited, and reservations were handled by human memory or ad-hoc notes, which caused mismatches and confusion.
The system must remain sheet-driven (Google Sheets = SSoT) and must respect existing recruitment workflows, thread-based onboarding, and render quota limits.

## **Decision**
We introduce a fully sheet-backed reservation system with:
* The new command:
  `!reserve <clantag>` — usable only by Recruiters and Admins, only inside ticket threads.
* A dedicated `RESERVATIONS_TAB` ledger containing:
  thread_id, ticket_user_id, recruiter_id, clan_tag, reserved_until (date), created_at, status, notes.
* Status values: `active`, `expired`, `released` (future), `cancelled` (optional).
* Two scheduled tasks:
  * **12:00 UTC reminder job** — warns if a reservation ends today.
  * **18:00 UTC auto-release job** — expires outdated reservations after a 6-hour grace period.
* Thread-level user notifications for creation, reminders, expiry.
* Recruiter-level logs posted to the configured `RECRUITERS_THREAD_ID`.
* Admins are always permitted to use reservation features (emergency override).
* All reservation functionality is gated by `FEATURE_RESERVATIONS` (`TRUE`/`FALSE`).
This provides a controlled, predictable, auditable workflow where reservations affect effective availability across the cluster.

## **Consequences**
* Recruiters have a consistent workflow for holding seats.
* Clan leads continue updating ingame open spots normally; nothing changes for them.
* The bot gains responsibility for deriving & updating availability values automatically.
* Reservations are no longer lost, forgotten, or silently overwritten.
* Required updates:
  * New command handler
  * Sheet adapter for `RESERVATIONS_TAB`
  * Integration in ticket threads
  * Scheduled reminder & auto-release tasks
  * Logging to threads + staff-log channel
* Future extensions (release/extend/list) can be added without breaking the model.

Doc last updated: 2025-11-13 (v0.9.7)
