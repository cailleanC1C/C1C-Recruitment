# Bot Permission Sync Runbook

This runbook documents the new `!perm bot` command group that manages
explicit channel overwrites for the shared **bot** role. The flow replaces the
old manual “grant Administrator” workaround while preserving least-privilege
access and an auditable trail.

## Overview

- Allow and deny lists live in `config/bot_access_lists.json` and are
  automatically created when absent.
- Category-level allows cascade to every child channel unless that channel is
  explicitly denied.
- Deny entries always take precedence over allow entries.
- Sync operations emit CSV audits in `AUDIT/diagnostics/` named
  `<guild>-YYYYMMDD_HHMM-bot_sync.csv`.
- A watcher listens for channel create/move events and reapplies overwrites when
  a channel lives under an allowed category.

## Access Lists

Run `!perm bot list` to display the current configuration. The report shows
counts and entries for the four buckets:

- Allowed categories
- Allowed channels
- Denied categories
- Denied channels

Pass `--json` to dump the raw payload (useful for backups or sharing a diff via
Git).

## Mutating the Lists

Each command accepts one or more channel references (`<#channel>`) or quoted
category names (`"Private Rooms"`). Targets are idempotent.

| Command | Description |
| --- | --- |
| `!perm bot allow <targets…>` | Adds channels/categories to the allow list and removes matching entries from the deny list. |
| `!perm bot deny <targets…>` | Adds channels/categories to the deny list and removes matching entries from the allow list. |
| `!perm bot remove <targets…>` | Removes targets from both allow and deny lists. |

Use the allow list for “default permit” scenarios and the deny list for
surgical blocks (for example, a single room inside an allowed category).

## Syncing Overwrites

`!perm bot sync` writes explicit overwrites for every channel that matches the
allow/deny rules. The command is admin-only and defaults to a dry run.

| Flag | Default | Description |
| --- | --- | --- |
| `--dry` | `true` | Preview the changes instead of writing them. Set `--dry false` to apply. |
| `--threads on|off` | persisted (default `on`) | Toggle thread creation/sending permissions. When applied live, this also updates the stored default. |
| `--include voice` | `off` | Include voice channels in the run. |
| `--include stage` | `off` | Include stage channels in the run. |
| `--limit N` | unlimited | Process at most `N` channels that require a write. Useful for staged rollouts. |

Running with `--dry false` posts a confirmation prompt; type `confirm` within
45 seconds to proceed. After a live run completes, the bot writes the audit CSV
and posts a short note to the CoreOps log channel. When errors occur the
sync summary lists an “Error details” section with the most common exception
messages, and the log note mirrors those reasons for fast triage.【F:modules/ops/permissions_sync.py†L864-L910】【F:modules/ops/permissions_sync.py†L1184-L1222】

### CSV Columns

| Column | Notes |
| --- | --- |
| `channel_id` | Discord channel snowflake. |
| `name` | Channel or category name at the time of sync. |
| `type` | Discord channel type (text, forum, category, etc.). |
| `category` | Parent category label if applicable. |
| `matched_by` | Which list produced the match (`category-allow`, `channel-deny`, etc.). |
| `prior_state` | Summary of the existing overwrite (or `missing`). |
| `action` | `created`, `updated`, `plan-create`, `plan-update`, `noop`, `skip-manual-deny`, or `skip-limit`. |
| `details` | Human-readable explanation for the action (error rows include the exception text returned by Discord). |

### Manual Deny Safeguard

If a channel already has `View Channel` explicitly denied for the bot role, the
sync skips it and records `skip-manual-deny`. Use this to freeze rooms that
should remain hidden even if their parent category is allowed.

## Watcher Behaviour

`modules/ops/watchers_permissions.py` hooks the following events:

- `on_guild_channel_create`
- `on_guild_channel_update` (category changes)

When a channel lands under an allowed category (or is individually allowed), the
watcher applies the same overwrite profile used by the manual sync. Skipped or
failed updates are logged for ops visibility.

## Storage Layout

`config/bot_access_lists.json` persists the lists and options:

```json
{
  "categories": {"allow": ["snowflake"], "deny": []},
  "channels": {"allow": [], "deny": ["snowflake"]},
  "options": {"threads_default": true},
  "updated_at": "ISO-8601"
}
```

- `threads_default` controls the default state for thread permissions during
  syncs and watcher events.
- Only the command group should mutate this file; manual edits are reserved for
  break-glass recovery.

Keep this document handy when onboarding new operators or auditing the bot’s
permissions footprint.

Doc last updated: 2025-11-17 (v0.9.8.2)
