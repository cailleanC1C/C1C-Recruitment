# Troubleshooting & Redaction

## Quick triage
- **Cron quiet** → confirm the latest `[cache]` refresh summary within the expected interval before
  triggering manual refreshes. If missing, inspect `/healthz` and deployment logs.
- **Command fails for staff** → confirm roles, then rerun with admin watching logs.
- **Watcher quiet** → check toggles in `!ops config` and verify `/healthz` for stale
  timestamps.
- **Cache stale** → run `!ops refresh all`; if it fails, capture the `[cron result]` and
  `[watcher|lifecycle]` lines around the attempt (dropping to `[lifecycle]` next release).
- **Sheets error** → switch to manual spreadsheet updates and note the outage window.

### Quick fixes
| Symptom | Likely Cause | Check Command |
| --- | --- | --- |
| `n/a` ages in `!digest` | Bot restarted → cache not yet warmed | wait 5 min or run `!ops refresh all` |
| “No tabs listed in Config” | Missing key in Sheet Config tab | check sheet permissions + tab names |
| “I can't find a configured welcome for **TAG**. Add it in the sheet.” | Row missing or inactive in `WelcomeTemplates`; confirm `ACTIVE` = `Y`. | Update the sheet then ask an admin to run `!welcome-refresh` |

Refer to the automation keys listed in [`Config.md`](Config.md#automation-listeners--cron-jobs)
when adjusting cadences or toggles.

## Feature toggles Q&A
- **Tab missing or misnamed?** Ensure the Config row `FEATURE_TOGGLES_TAB → FeatureToggles`
  exists in the recruitment Sheet. Missing tabs fail closed and trigger a single
  admin-ping warning in the runtime log channel.
- **Headers wrong?** The worksheet must expose `feature_name` and `enabled`. Fix the
  headers, save, then run `!ops reload` and re-verify with `!checksheet`.
- **Row missing?** Add the feature row using the approved key and `enabled` value. Rows
  absent from the worksheet evaluate to disabled until present.
- **Value ignored?** Only `TRUE` (case-insensitive) enables a feature. Any other value —
  including `FALSE`, blanks, or typos — keeps the module off and logs an admin-ping
  warning.
- **Change not taking effect?** After editing the Sheet, run `!ops reload`, then
  confirm with `!checksheet` to ensure the worksheet and headers are clean.

## Redaction policy
- Secrets display as `(masked)` with only the final four characters visible.
- High-sensitivity keys (tokens, service accounts) never appear in embeds or logs.
- Runtime logging strips any field flagged as secret before sending to Discord.

## Health probes
- `/ready` — Render routing check (lightweight).
- `/healthz` — Includes watchdog metrics, cache timestamps, and watcher toggles.
- `!health` — Mirrors `/healthz` output in Discord for admins.

## Log taxonomy
- `[cron]` — scheduled jobs (start/result/retry/summary, duration, error).
- `[lifecycle]` — watcher lifecycle notices and failure reports (logged as
  `[watcher|lifecycle]` during the dual-tag release).
- `[refresh]` — manual cache warmers (bucket, trigger, duration, result, error).
- `[command]` — RBAC checks and command outcomes.

## Escalation notes
- Capture timestamp, guild ID, command or watcher name, and the exact log line when
  opening an incident.
- Ping #bot-production with the summary before filing a longer report.

Doc last updated: 2025-10-31 (v0.9.7)
