# Ops — CoreOps Runbook (v0.9.3-phase3b-rc3)

CoreOps gives staff and admins a quick view into the bot's health without leaving the
Discord channel.

## Guild-only access
CoreOps commands only respond in guild text channels. Direct messages receive a friendly
denial, even for Admins.

## Command reference

| Command | Access |
| --- | --- |
| `!rec config` / `!config` | Admin-only |
| `!rec reboot` | Admin-only |
| `!rec reload` | Admin-only |
| `!rec refresh all` | Admin-only |
| `!rec health` / `!health` | Admin-only |
| `!rec checksheet` | Admin-only |
| `!rec env` / `!env` | Admin-only |
| `!rec digest` / `!digest` | Staff & Admin |
| `!rec refresh clansinfo` | Staff & Admin |
| `!rec ping` / `!ping` | Public |

Admin bang shortcuts call the same handlers as their `!rec` versions. RBAC checks apply
before execution.

## `!env`

- **Access** — Admin-only. Administrator permission is a fallback when no configured
  role is present.
- **Sections** — Output is grouped (Core Identity, Guild / Channels, Roles, Sheets,
  Secrets).
- **Masking** — Secrets show `(masked)` with the last four characters visible.
- **Lookup** — Guild, channel, and role IDs resolve to names with cached lookups.

Sample excerpt:

```
Core Identity
ENV_NAME: production
BOT_VERSION: v0.9.3-phase3b-rc3

Secrets
SERVICE_ACCOUNT_KEY: ****9f2c (masked)
WEBHOOK_TOKEN: ****71ab (masked)
```

## Refresh and cache management

Cache refresh commands live directly in the shared CoreOps cog:

- `!rec refresh all` — Admin-only. Clears and warms every registered Sheets cache bucket
  in the background. Emits a `[refresh]` log to `LOG_CHANNEL_ID` with the trigger
  (`manual` or `schedule`) and actor.
- `!rec refresh clansinfo` — Staff/Admin. Refreshes the `clans` cache when it is at least
  60 minutes old; otherwise reports its freshness and the next scheduled refresh window.
  The same `[refresh]` log is emitted when the guard passes.

All manual refreshes respect the 60 minute guard to avoid spamming Sheets. Results
(success, retry, cancel, failure) surface in Discord and the log stream. Log lines follow
`[refresh] bucket=<name> trigger=<manual|schedule> actor=<@user> duration=<ms> result=<state> error=<text>`.

Cache TTL reference:

| Bucket | TTL |
| --- | --- |
| `clans` | 3 hours |
| `templates` | 7 days |
| `clan_tags` | 7 days |

Scheduled refresh cadence:

- `clans` — every 3 hours.
- `templates` & `clan_tags` — weekly, Mondays at 06:00 UTC.

Phase 3b shared Ops work resumes after this fix, once refresh command coverage is stable
across environments.

### `refresh all` summary embed

Manual runs now emit a single summary embed covering every cache bucket. Example layout:

```
Refresh Summary — manual by @AdminUser

Buckets
| Bucket | Result | Retries | Duration |
| --- | --- | --- | --- |
| clans | success | 0 | 842 ms |
| templates | retry (success) | 1 | 1935 ms |
| clan_tags | cancelled | 0 | 0 ms |

Total duration: 2,777 ms
```

The embed footer follows the shared footer builder and uses the message timestamp for
context.

## Sample outputs
- **Health** — Embed with gateway latency, cache metrics, heartbeat timestamps (READY/connect/disconnect),
  watchdog stall timers, and Render readiness. Example cache block:

  ```
  Cache
  clans: age 47m • TTL 3h • next in 2h
  templates: age 5d • TTL 7d • next overdue by 6h
  ```
- **Digest** — One-line summary: bot version, watchdog state, last heartbeat age.
- **Help footer** — `Bot v{BOT_VERSION} · CoreOps v{COREOPS_VERSION}` (timestamp supplied by the
  embed).

## Embed footer

All CoreOps/admin embeds use the unified footer builder: `Bot v{BOT_VERSION} · CoreOps
vA.B.C` with optional notes appended using ` • `. Inline datetimes are removed—rely on
the embed timestamp Discord displays beneath the message.

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

_Doc last updated: 2025-10-16 (v0.9.3-phase3b-rc3)_
