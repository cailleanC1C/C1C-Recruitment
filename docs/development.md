# Development — v0.9.3-phase3b-rc4

This document covers how Caillean and Codex iterate on the recruitment runtime using the
web-based deployment flow. Local execution is not supported in Phase 3b.

## Phase 3b workflow
- Ship changes through the shared Render pipelines exposed in the admin portal.
- Use the deployment queue controls to pause/resume production refreshes when rolling out
  CoreOps updates.
- Update PR descriptions with the required metadata block (see
  [Command System Guide](commands.md#adding-new-commands-internal-guide)).

## Environment configuration checks
- Version config lives in the Sheets **Config** tab and propagates automatically during
  refresh.
- Verify guild role IDs before deployment; `is_admin_member()` and `is_staff_member()` rely
  on those mappings.
- Refresh caches post-deploy with `!rec refresh clansinfo` (staff) or `!rec refresh all`
  (admin) as needed.

## Command system verification
- `!rec help` shows user and staff tiers depending on the caller. Expect no denial copy
  during help rendering.
- `!help` is admin-only and lists every command grouped by tier.
- Use `rehydrate_tiers()` followed by `audit_tiers()` inside the Render console when
  validating tier coverage.
- See [Command System Guide](commands.md) and the
  [CoreOps contract](coreops_contract.md) for details on RBAC helpers and escalation.

## Project layout quick reference
- Core cogs live in `modules/`; CoreOps loads from `modules.coreops`.
- Tier metadata is declared in `shared/coreops/helpers/tiers.py`.
- RBAC helpers reside in `shared/coreops_rbac.py` and gate privileged commands.
- The command tree is configured in `app.py` when the bot boots.

---

_Doc last updated: 2025-10-17 (v0.9.3-phase3b-rc4)_
