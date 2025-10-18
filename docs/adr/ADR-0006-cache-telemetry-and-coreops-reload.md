# ADR-0006 — Public cache telemetry wrapper + CoreOps reload consolidation

## Context:
  Phase 3b harmonization; prior bots accessed private cache internals and duplicated reload/reboot logic.
## Decision:
  • Create shared/cache/telemetry.py with public read-only API.
  • Keep !refresh for cache/data refreshes only.
  • Keep !reload for config reload; add --reboot flag for graceful exit.
  • Enforce fail-soft I/O and admin RBAC.
## Consequences:
  Simplifies ops parity, removes duplication, consistent telemetry source.
## Alternatives:
  Separate !reload/!reboot commands — rejected as redundant.
## Links:
  Phase 3b issue tracker and REPORT_PR5_STATUS.md
## Status: 
Accepted — 2025-10-18
