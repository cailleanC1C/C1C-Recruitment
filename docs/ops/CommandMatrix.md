# Command Matrix — Phase 3b

This matrix consolidates the former command guide and CoreOps contract. Every command is
listed with its tier, status, and operational ownership. Use it when verifying help output
or walking through incident playbooks. Status values mirror the Ops Command Tracking sheet:
`done` (live), `polish` (functionally complete but still getting final copy/QA), and `open`
(backlog items we intend to carry forward).

## Implementation status — done
| Command | Tier | Type | Notes |
| --- | --- | --- | --- |
| `!help` | Admin | CoreOps | Admin view of the tiered help catalog (bang alias for `!rec help`). |
| `!rec help` | User / Staff | CoreOps | Tier-aware help renderer surfaced to all tiers. |
| `!ping` / `!health` | Admin | CoreOps | Liveness snapshot with uptime, latency, and watchdog stats. |
| `!rec ping` | User | CoreOps | Member-facing latency check surfaced via `!rec help`. |
| `!env` | Admin | CoreOps | Masked environment + configuration overview for deployments. |
| `!rec digest` | Staff | CoreOps | Manual trigger for the recruiter digest line. |
| `!rec refresh clansinfo` | Staff | CoreOps | Refreshes the clans cache when the guard window permits. |
| `!rec refresh all` | Admin | CoreOps | Warms every registered cache bucket with a bucket-by-bucket report. |
| `!rec health` | Admin | CoreOps | Staff/admin health embed; QA pass pending updated help text. |


## Implementation status — polish
| Command | Tier | Type | Notes |
| --- | --- | --- | --- |
| `!rec help` (detail embeds) | User / Staff | CoreOps | Help detail embed refresh aligned with new footer styling. |


## Implementation status — open
| Command | Tier | Type | Notes |
| --- | --- | --- | --- |
| `!backfill_tickets` | Admin | App (Onboarding) | Manual welcome/promo backfill port; staged in AUDIT backlog. |
| `!backfill_stop` | Admin | App (Onboarding) | Cancel hook for the backfill worker. |
| `!backfill_details` | Admin | App (Onboarding) | Export skipped/updated rows from the last backfill. |
| `!checksheet` | Admin | CoreOps | Validates that required Sheets tabs and named ranges exist. |
| `!clan <tag>` | User | App (Recruitment) | Clan profile lookup sourced from Sheets. |
| `!clanmatch` | Staff | App (Recruitment) | recruiter panel; backend enabled, UI gated behind feature flag. |
| `!clansearch` | Staff | App (Recruitment) | clan search; shares matcher backend and remains feature-flagged off. |
| `!rec config` | Staff | CoreOps | Staff-visible config summary (guilds, sheets, feature flags). |
| `!rec config` (detail view) | Admin | CoreOps | Hidden admin alias; copy review pending before exposing in help. |
| `!welcome` (panels) | Staff | App (Onboarding) | Panel-driven welcome variant; blocked on final embed polish. |
| `!welcome` | Staff | App (Onboarding) | Posts a templated welcome note to the configured channel. |

## RBAC & help expectations
- All tier checks run through `shared.coreops.helpers.tiers` and
  `shared.coreops_rbac`.
- Help rendering always succeeds even if a command is gated; commands that cannot execute
  simply return “Admin only.” or “Staff only.”
- Every command in this matrix appears in the help output unless explicitly hidden via
  `cmd.extras["hide_in_help"]`. Hidden admin aliases are tracked in the matrix so they are
  discoverable during audits.

## Operational checklist
- Verify recruiter/admin roles each deploy (`is_staff_member`, `is_admin_member`).
- After cache refreshes, check `[refresh]` logs for duration and error fields.
- Incident response: capture timestamp, guild ID, command, and relevant log snippet in the
  issue tracker.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
