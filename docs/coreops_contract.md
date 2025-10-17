# CoreOps Command Contract — v0.9.3-phase3b-rc4

CoreOps provides diagnostics, cache management, and environment visibility for recruiters
and admins. This contract documents the command matrix, RBAC expectations, and escalation
paths after the Phase 3b command and tiering refactor.

## Scope & access

- All commands must be run from guild text channels. DM usage returns a friendly denial.
- Only the configured Admin or Staff roles (as defined in config) can access CoreOps
  commands.
- Prefix support: `!` or a direct mention (e.g. `@C1C Recruitment`). Admin bang shortcuts
  execute the same handlers as their `!rec` counterparts.

## RBAC and incident handling

- Role checks rely solely on the helpers `is_admin_member()` and `is_staff_member()`.
- Decorators such as `@ops_only("admin")` and `@ops_only("staff")` wrap these helpers and
  emit denial messages ("Admin only.", "Staff only.") only during command execution.
- Help output is side-effect free. Rendering help never leaks configuration or secrets.
- Log denials in `LOG_CHANNEL_ID` only once per 30 seconds per member + command to avoid
  spam. The throttling is implemented within the shared RBAC helpers.
- If cache refreshes fail twice in a row or env dumps mask unexpected values, escalate to
  platform engineering with the log snippet.

## Command reference (Phase 3b)

| Command | Tier | Purpose |
| --- | --- | --- |
| `!help` | Admin | Renders the admin-only help view with all tiers.
| `!ping` / `!health` | Admin | Plain shortcuts for liveness and latency checks.
| `!rec refresh all` | Admin | Clears and warms every Sheets cache bucket in the background.
| `!reload` | Admin | Hot-reloads loaded extensions without restarting the process.
| `!checksheet` | Admin | Validates that required Sheets tabs and named ranges exist.
| `!env` | Admin | Dumps env, guild, channel, and role mappings (safely masked).
| `!rec config` | Staff | Echoes relevant runtime config (no secrets).
| `!rec digest` | Staff | Posts the daily digest on demand.
| `!rec refresh clansinfo` | Staff | Refreshes the clans cache when the guard window expires.
| `!welcome` | Staff | Posts a templated welcome for a placement.
| `!rec ping` | User | Tier-aware latency check surfaced via `!rec help`.

Refer to [docs/commands.md](commands.md) for the full command catalog including public
commands and help behavior.

## Cache refresh policy

- `!rec refresh all` always respects a 60-minute guard per bucket. When denied by the
  guard, it responds with the current age and next eligible window.
- `!rec refresh clansinfo` shares the same guard. Recruiters should prefer scheduled
  refreshes unless a placement requires a fresh lookup.
- Manual refreshes emit a `[refresh]` log with the trigger (`manual` or `schedule`), actor,
  result, and duration.

## `!env` response contract

- Sections: **Core Identity**, **Guild / Channels**, **Roles**, **Sheets**, **Secrets**.
- Secrets are masked to the last four characters (e.g. `****9f2c`).
- Unknown IDs resolve to `unknown:<id>` so admins can fix misconfigurations quickly.

## Escalation matrix

1. Cache refresh failures (`result=failure` twice) — notify platform engineering.
2. RBAC misconfigurations (admins denied valid commands) — verify role IDs, then escalate
   if helper functions misbehave.
3. Render deploy drift (command tree mismatch) — run `!rec digest`, capture version +
   commit, and escalate via the deployment channel.

---

_Doc last updated: 2025-10-17 (v0.9.3-phase3b-rc4)_
