# Ops — CoreOps Runbook (v0.9.3)

CoreOps gives staff and admins a quick view into the bot's health without leaving the
Discord channel.

## Access levels
- **Admin roles (`ADMIN_ROLE_IDS`)** — Full access. Can run every CoreOps command and use
  the bang shortcuts.
- **Staff roles (`STAFF_ROLE_IDS`)** — Access to the standard `!rec` commands only.

## Commands by role

| Command | Staff | Admin |
| --- | --- | --- |
| `!rec help` | ✅ | ✅ |
| `!rec ping` | ✅ | ✅ |
| `!rec digest` | ✅ | ✅ |
| `!rec health` | ✅ | ✅ |
| `!rec env` | ✅ | ✅ |
| `!config` | ✅ | ✅ |
| `!rec refresh clansinfo` | ✅ | ✅ |
| `!rec refresh all` | ❌ | ✅ |
| `!health`, `!env`, `!digest`, `!help`, `!ping` | ❌ | ✅ |

## Admin bang shortcuts
Admins can use the `!health`, `!env`, `!digest`, `!help`, and `!ping` aliases without
`!rec`. The shortcuts call the same handlers, so responses match the prefixed versions.

## Refresh and cache management

Cache refresh commands live directly in the shared CoreOps cog:

- `!rec refresh all` — Admin-only. Clears and warms every registered Sheets cache bucket in the background. Emits a `[refresh]` log to `LOG_CHANNEL_ID` with the trigger (`manual` or `schedule`) and actor.
- `!rec refresh clansinfo` — Staff/Admin. Refreshes the `clans` cache when it is at least 60 minutes old; otherwise reports its freshness and the next scheduled refresh window. The same `[refresh]` log is emitted when the guard passes.

All manual refreshes respect the 60 minute guard to avoid spamming Sheets. Results (success, retry, cancel, failure) surface in Discord and the log stream. Log lines follow `[refresh] bucket=<name> trigger=<manual|schedule> actor=<@user> duration=<ms> result=<state> error=<text>`.

Cache TTL reference:

| Bucket | TTL |
| --- | --- |
| `clans` | 3 hours |
| `templates` | 7 days |
| `clan_tags` | 7 days |

Scheduled refresh cadence:

- `clans` — every 3 hours.
- `templates` & `clan_tags` — weekly, Mondays at 06:00 UTC.

Phase 3b shared Ops work resumes after this fix, once refresh command coverage is stable across environments.

## Sample outputs
- **Health** — Embed with gateway latency, cache metrics, heartbeat timestamps (READY/connect/disconnect),
  watchdog stall timers, and Render readiness. Example cache block:

  ```
  Cache
  clans: age 00:47:12 • TTL 03:00:00 • next 2025-10-16 18:00 UTC
  templates: age 05d 04:00 • TTL 07d 00:00 • next 2025-10-20 06:00 UTC
  ```
- **Digest** — One-line summary: bot version, watchdog state, last heartbeat age.
- **Help footer** — `Bot v{BOT_VERSION} • CoreOps v1.0.0 • 2025-10-14 12:00 Vienna` (falls
  back to UTC if the Vienna timezone is unavailable).

## Common issues
1. **Prefix mismatch** — Ensure commands start with `!rec`, `rec`, or a bot mention. Admin
   shortcuts only work for Admin role holders.
2. **Missing roles** — Confirm the Admin or Staff role IDs are applied to the member.
3. **Intents disabled** — Enable the Server Members intent so role data arrives.
4. **Watchdog warnings** — Review logs for stall or disconnect alerts; Render will restart
   the container on exit.

## When to escalate
If CoreOps is offline or watchdog reconnects loop for more than a few minutes, alert the
platform team. Provide recent `/healthz` responses and any watchdog stall logs.

---

_Doc last updated: 2025-10-16 (v0.9.3)_
