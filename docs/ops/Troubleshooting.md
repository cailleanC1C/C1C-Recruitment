# Troubleshooting & Redaction — Phase 3b

## Quick triage
- **Cron quiet** → confirm the latest `[cron result]` within the expected interval before
  triggering manual refreshes. If missing, inspect `/healthz` and deployment logs.
- **Command fails for staff** → confirm roles, then rerun with admin watching logs.
- **Watcher quiet** → check toggles in `!rec config` and verify `/healthz` for stale
  timestamps.
- **Cache stale** → run `!rec refresh all`; if it fails, capture the `[cron result]` and
  `[watcher]` lines around the attempt.
- **Sheets error** → switch to manual spreadsheet updates and note the outage window.

Refer to the automation keys listed in [`Config.md`](Config.md#automation-listeners--cron-jobs)
when adjusting cadences or toggles.

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
- `[watcher]` — watcher lifecycle notices and failure reports.
- `[refresh]` — manual cache warmers (bucket, trigger, duration, result, error).
- `[command]` — RBAC checks and command outcomes.

## Escalation notes
- Capture timestamp, guild ID, command or watcher name, and the exact log line when
  opening an incident.
- Ping #bot-production with the summary before filing a longer report.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
