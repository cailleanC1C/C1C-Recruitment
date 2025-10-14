# Documentation Refresh Notes

- Added Phase 1 baseline entry to `CHANGELOG.md` covering CoreOps, watchdog, heartbeat,
  RBAC, prefix handling, health server, and deploy workflow fixes.
- Rewrote the root `README.md` for guild users with new command guidance, expectations,
  privacy stance, and support tips.
- Expanded `modules/coreops/README.md` for staff/admin usage: command catalog, RBAC roles,
  admin bang shortcuts, help footer timezone, and troubleshooting steps.
- Renamed docs to lowercase and refreshed:
  - `docs/architecture.md` now diagrams the gateway, heartbeat tracker, watchdog, health
    server, command layer, and Render restart behavior.
  - `docs/development.md` documents Python 3.12 setup, intents, run commands, prefix tests,
    project layout, and style guidance.
  - `docs/ops.md` outlines environment variables, intents, GitHub Actions → Render deploy
    flow, health endpoints, and RBAC troubleshooting.
  - `docs/readme.md` indexes the updated documentation set with descriptions.
  - `docs/ops_coreops.md` serves as a CoreOps runbook including role access, shortcuts,
    sample outputs, failure modes, and escalation guidance.
- Captured the aggregate diff in `DOCS_PATCH.diff` for review packaging.
