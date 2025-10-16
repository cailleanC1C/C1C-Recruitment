# Ops — CoreOps Runbook (v0.9.2)

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
| `!health`, `!env`, `!digest`, `!help`, `!ping` | ❌ | ✅ |

## Admin bang shortcuts
Admins can use the `!health`, `!env`, `!digest`, `!help`, and `!ping` aliases without
`!rec`. The shortcuts call the same handlers, so responses match the prefixed versions.

## Refresh and cache management

CoreOps hosts two command groups for cache control:

- `!refresh` (admin-only):
  - `!refresh all` — Clear and warm every registered Sheets cache bucket.
- `!rec refresh` / `!rec_refresh`:
  - `all` — Admin alias for `!refresh all`.
  - `clansinfo` — Staff/Admin tool that refreshes the `clans` cache if it is older than 60 minutes; otherwise it reports the next scheduled refresh.

Cache TTL reference:

| Bucket | TTL |
| --- | --- |
| `clans` | 15 minutes |
| `templates` | 15 minutes |
| `clan_tags` | 60 minutes |

Phase 3b shared Ops work resumes after this fix, once refresh command coverage is stable across environments.

## Sample outputs
- **Health** — Embed with gateway latency, heartbeat timestamps (READY/connect/disconnect),
  watchdog stall timers, and Render readiness.
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

_Doc last updated: 2025-10-15 (v0.9.2)_
