# ADR-0024 — Housekeeping audit + recruiter ticket digest
Date: 2025-12-02

## Context
- Stray members sometimes keep Raid after losing clan tags; others keep clan tags
  while being marked as Wandering Souls.
- Visitors can linger without tickets or pick up extra roles without automated
  visibility.
- Recruiters lacked a consolidated view of currently open Welcome and Move
  Request tickets alongside the Daily Recruiter Update.
- Render-friendly operations require scheduled HTTP triggers instead of
  long-lived polling loops or databases.

## Decision
- Add a scheduled role & visitor audit that:
  - Removes Raid and adds Wandering Souls when no clan tags are present.
  - Removes Raid from existing Wanderers with no clan tags.
  - Reports (without auto-fix) Wandering Souls carrying clan tags plus Visitor
    buckets (no tickets, closed-only tickets, extra roles).
  - Posts a single summary to `ADMIN_AUDIT_DEST_ID` per run.
- Add a "Currently Open Tickets" digest that lists open Welcome and Move Request
  threads (W/R/M/L codes) by creation time in `REPORT_RECRUITERS_DEST_ID`.
- Piggyback on the existing Daily Recruiter Update scheduler so the audit and
  open-ticket digest run alongside the recruiter report without needing a
  separate cron endpoint or token.

## Consequences
- New env keys cover role IDs, audit destination, and ticket channel
  dependencies; `.env.example` and Config docs stay in sync.
- Admins gain daily visibility into role corrections and Visitor outliers with
  minimal Discord mutations.
- Recruiters receive a timestamped open-ticket list, reducing the chance of
  missed Welcome or Move Request threads.
- Keeping the existing scheduler avoids new HTTP surface area while still
  running the new reports on the established cadence.

Status: Approved

Doc last updated: 2025-12-04 (v0.9.7)
