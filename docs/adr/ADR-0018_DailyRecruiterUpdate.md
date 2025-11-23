# ADR-0018 — Daily Recruiter Update v1

**Date:** 2025-10-26  
**Status:** Accepted (Final)  
**Related Epic:** Phase 6 — Daily Recruiter Update (Reporting v1)

---

## Context
The Recruitment bot needed a simple, reliable way to surface daily recruitment statistics from the shared Mirralith spreadsheet (tab `Statistics`). Previous Matchmaker code had an embedded daily loop but was tied to sheet shape, local time conversions, and duplicate cache logic. WelcomeCrew had only partial status reporting. We wanted a unified daily report that fits our current bot conventions, CoreOps logging format, and existing refresh system.

The sheet structure was standardized:  
- Config tab defines `REPORTS_TAB` (default `Statistics`).  
- `Statistics` tab holds a *General Overview* block (Overall, Top 10, Top 5) and a *Per Bracket* block (Elite End Game → Beginners).

The report must:
- run daily at a fixed **UTC** time (`REPORT_DAILY_POST_TIME`),
- also run on demand via `!report recruiters` (admin-only),
- post into a configured Discord destination (`REPORT_RECRUITERS_DEST_ID`),
- read only the prepared sheet (no cache warmers or direct gspread calls),
- output the familiar “Summary Open Spots” embed consistent with other bot embeds, and
- follow our global logging pattern for auditability.

---

## Decision
We implemented a new **reporting pipeline** under `modules/recruitment/reporting/`.

### Core decisions
- **UTC-only scheduling** — `REPORT_DAILY_POST_TIME` is interpreted as UTC; no timezone conversion or offset math.
- **Source of truth:** `REPORTS_TAB` from Config sheet (default `Statistics`).
- **Feature toggle:** `recruitment_reports` governs both scheduled and manual triggers.
- **Single env destination:** `REPORT_RECRUITERS_DEST_ID` — channel or thread ID.
- **Sheet parsing:**
  - Use header names, not hard indexes.
  - Collect rows under “General Overview” until “Per Bracket.”
  - In “Per Bracket,” detect headers in column B: `Elite End Game`, `Early End Game`, `Late Game`, `Mid Game`, `Early Game`, `Beginners`.
  - Render only rows where any of open/inactive/reserved > 0.
- **Output formatting:**
  - Message body: `# Update YYYY-MM-DD` then mentions built from `RECRUITER_ROLE_IDS`.
  - Embeds: two-card payload (`Summary Open Spots` for overview + per-bracket rollups, `Bracket Details` for clan-level lines).
  - Bullet format: `🔹 **Label:** open X | inactives Y | reserved Z` for all summary and detail lines.
  - Footer: `last updated {UTC timestamp} • daily UTC snapshot` on the Summary embed.
- **Logging:** every success/failure line uses existing CoreOps style, e.g.  
  `[report] recruiters • actor=scheduled guild=<id> dest=<id> date=YYYY-MM-DD result=ok error=-`.
- **CoreOps integration:**
  - `!env` exposes the new env vars (`REPORT_DAILY_POST_TIME`, `REPORT_RECRUITERS_DEST_ID`).
  - `!checksheet` includes `REPORTS_TAB`.
  - `!help` documents the new command.
- **RBAC:** `!report recruiters` is admin-gated via existing CoreOps role utilities.
- **No stale logic:** each post is a single daily snapshot.

---

## Consequences
**Benefits**
- Consistent embed look with all other C1C bot messages.
- One unified UTC schedule simplifies ops; no timezone surprises.
- Report reads only from curated sheet data — minimal runtime overhead.
- Fewer failure points; no duplicate caching or external pulls.
- Immediate visibility in the log channel for every post or error.

**Trade-offs**
- Relies entirely on the external sheet being up-to-date; no in-bot fallback.
- Adding metrics later will require expanding sheet schema and parser.
- The UTC-only schedule may feel less intuitive for admins expecting local time.

**Operational impact**
- Admins configure three things: toggle on, set destination, set UTC time.
- CoreOps shows and validates envs; `!checksheet` confirms tab visibility.
- Failure logs mirror our standard pattern; no special monitoring required.

---

## Implementation summary
| Component | Location | Notes |
|------------|-----------|-------|
| Scheduler loop | `daily_recruiter_update.py` | Runs at `REPORT_DAILY_POST_TIME` UTC |
| Manual command | `!report recruiters` | Admin-gated trigger |
| Formatter | same module | Builds embeds + message body |
| Config | `.env` + Sheets Config tab | Supplies time, dest, and tab name |
| Logging | CoreOps logger | Reuses `[report]` format |
| Docs | `docs/adr/ADR-0018.md`, README, CommandMatrix, Config docs | Updated accordingly |

---

## Status
Final. Shipped with **Phase 6 — Reporting v1**. Feature toggle `recruitment_reports` defaults ON (`TRUE`) and remains enabled across environments; disable it only when the Sheet or destination is misconfigured.

Doc last updated: 2025-11-23 (v0.9.7)
