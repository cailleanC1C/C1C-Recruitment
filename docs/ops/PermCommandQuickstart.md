# `!perm bot` Quickstart

The `!perm` command surface lets Core Ops admins maintain the allow/deny lists
that drive the automated bot-role permission sync. Every sub-command in the
`bot` group is protected by the `admin_only` decorator, so it can only be run by
Core Ops staff inside a guild.【F:modules/ops/permissions_sync.py†L905-L917】

## Listing the current state

```text
!perm bot list [--json]
```

`list` renders an embed that counts the allowed/denied categories and channels
stored in `config/bot_access_lists.json`. Pass `--json` (or `-j`) to receive the
raw snapshot payload in code blocks for archival or diffing.【F:modules/ops/permissions_sync.py†L919-L970】【F:modules/ops/permissions_sync.py†L108-L117】

## Allow / deny / remove targets

All mutating commands accept any mix of channel mentions, raw channel IDs, or
quoted category names. Arguments are tokenised with `shlex.split`, so wrap
multi-word category names in quotes. Duplicate entries are ignored automatically
thanks to the `ChannelOrCategoryConverter` and the store’s idempotent writes.【F:modules/ops/permissions_sync.py†L750-L808】【F:modules/ops/permissions_sync.py†L782-L808】【F:modules/ops/permissions_sync.py†L829-L884】

- `!perm bot allow …` moves the targets into the allow list and clears matching
  entries from the deny list.
- `!perm bot deny …` does the inverse, preferring the deny list when overlap
  occurs.
- `!perm bot remove …` strips the targets from both lists without adding them
  anywhere.【F:modules/ops/permissions_sync.py†L999-L1096】

Replies include a human-readable summary of the categories/channels touched so
operators can double-check the outcome.【F:modules/ops/permissions_sync.py†L810-L848】【F:modules/ops/permissions_sync.py†L1034-L1056】

## Running a sync

```text
!perm bot sync [--dry false] [--threads on|off] [--include voice,stage] [--limit N]
```

Syncs are dry runs by default. Setting `--dry false` triggers an interactive
confirmation step (`confirm` within 45 s) before applying changes. During the
live run the command writes an audit CSV and logs a summary with counts for
created/updated overwrites and any errors.【F:modules/ops/permissions_sync.py†L1100-L1217】

Optional flags mirror the implementation:

- `--threads` accepts `on/off` (or truthy/falsey aliases) to override the stored
  default; live syncs also persist the new default for future runs.【F:modules/ops/permissions_sync.py†L1138-L1182】【F:modules/ops/permissions_sync.py†L713-L734】
- `--include` accepts space- or comma-separated tokens; the recognised values
  are `voice` and `stage`.
- `--limit` ensures only the first N channels needing writes are processed; the
  value must be positive.【F:modules/ops/permissions_sync.py†L1138-L1182】

Use a dry run first to inspect the summary (planned overwrites, skips, limit
hits). Once satisfied, re-run with `--dry false`, confirm, and review the final
summary plus the emitted CSV in `AUDIT/diagnostics/` if deeper auditing is
needed.【F:modules/ops/permissions_sync.py†L1184-L1215】【F:modules/ops/permissions_sync.py†L676-L705】

### Reading the sync summary

The embed lines map directly to the `SyncReport` payload. These highlights help
interpret “zero applied” scenarios such as a sync that matches many channels but
doesn’t need to touch any overwrites:

- **Matched channels** counts everything that the allow/deny lists cover, even
  if they already have the correct overwrite. It mirrors
  `len(matched_plans)`.【F:modules/ops/permissions_sync.py†L524-L556】
- **Processed** only increments when a channel actually needs a change and is
  within the optional `--limit`. If all channels are already up-to-date, this
  value (and the applied count) will stay at zero, which is expected.【F:modules/ops/permissions_sync.py†L555-L683】
- **No-ops** reflects channels that matched the lists but required no writes; a
  non-zero value here confirms nothing was wrong—every overwrite already matched
  the desired state.【F:modules/ops/permissions_sync.py†L579-L593】

If something truly fails you will see the **Errors** line, an “Error details”
section that groups the exception messages Discord returned (for example,
`Missing Permissions`), and corresponding `error` entries in the CSV so you can
pinpoint the affected channels. The log message sent to Core Ops also echoes the
top reasons in brackets for quick triage. Otherwise a “zero applied” run simply
means the bot role already has the correct permissions everywhere.【F:modules/ops/permissions_sync.py†L630-L707】【F:modules/ops/permissions_sync.py†L1184-L1222】
