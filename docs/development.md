# Development — Phase 3b

## Workflow snapshot
- Deploy via the shared Render pipelines; local execution is unsupported this phase.
- Use PR descriptions with the required metadata block (see template below).
- Pause the deployment queue before force-pushing or re-running builds.

### Required PR metadata
```
[meta]
labels: docs, comp:ops-contract, P2
milestone: Harmonize v1.0
[/meta]
```

## Contribution checklist
1. Branch from `main` and follow commit conventions.
2. Update documentation alongside code changes.
3. Run smoke checks or targeted tests where applicable.
4. Include rollout notes for staff when features need coordination.
5. Confirm help tiers using `rehydrate_tiers()` + `audit_tiers()` in a staging session.

## Command & embed style
- Declare tiers with `@tier("user"|"staff"|"admin")`; gate execution via
  `shared.coreops_rbac` helpers (`is_admin_member`, `is_staff_member`).
- Approved help description (keep formatting):
  ```
  C1C-Recruitment keeps the doors open and the hearths warm.
  It’s how we find new clanmates, help old friends move up, and keep every hall filled with good company.
  Members can peek at which clans have room, check what’s needed to join, or dig into details about any clan across the cluster.
  Recruiters use it to spot open slots, match new arrivals, and drop welcome notes so nobody gets lost on day one.
  All handled right here on Discord — fast, friendly, and stitched together with that usual C1C chaos and care.
  ```
- Embed titles: sentence case (`Feature · Context`).
- Footers: `Bot vX.Y.Z · CoreOps vA.B.C`, optional extras appended with ` • `.
- Always set the embed timestamp instead of hard-coding dates in fields.

## Doc map
| Audience | Where to start |
| --- | --- |
| Members | [`README.md`](../README.md) |
| Operators | [`docs/ops/Runbook.md`](ops/Runbook.md) |
| Config owners | [`docs/ops/Config.md`](ops/Config.md) |
| Developers | [`docs/development.md`](development.md) + [`docs/Architecture.md`](Architecture.md) |
| Watcher maintainers | [`docs/ops/Watchers.md`](ops/Watchers.md) |
| Incident responders | [`docs/ops/Troubleshooting.md`](ops/Troubleshooting.md) |

## Lessons learned (see `AUDIT/`)
- Keep refresh durations under 60 seconds; longer runs risk Render restarts (Audit 2025-09-12).
- Escalate Sheets outages immediately; prior incidents show data divergence within 15
  minutes when watchers continue writing (Audit 2025-08-04).
- Document toggle changes in PRs; missing notes slowed response during the Phase 3 rollout
  (Audit 2025-07-22).

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
