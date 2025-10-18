# Ops Runbook — Phase 3b

## Daily expectations
- Confirm the bot is online and responding to `!ping` in production.
- Review scheduled refresh logs via `[cron]` entries for duration anomalies.
- Check the welcome and promo ticket channels for stuck threads or duplicate posts.

### Logs to check
1. `[ops]` — service lifecycle messages (boot, shutdown, deploy tags).
2. `[watcher]` — event listeners (toggles, hook errors, ticket IDs).
3. `[cron]` — scheduled jobs (start/result/retry/summary for refresh cycles).

_If `[cron]` lines stop appearing for longer than the configured cadence, assume the
scheduler is stalled and inspect `/healthz` before triggering manual refresh commands._

## Deployment checklist
1. Ship through the Render pipeline (GitHub Actions handles image builds).
2. Pause the deployment queue if multiple releases are queued; resume when ready.
3. After deploy, run `!rec help` (user account) and `!help` (admin) to verify tier
   listings.
4. Trigger `!rec refresh clansinfo` and watch for the success log with duration < 60s.

## Incident handling
| Scenario | Immediate actions | Follow-up |
| --- | --- | --- |
| Command denial for staff | Confirm role IDs in config, run `!rec config`, re-sync roles | File ticket with timestamp + member ID |
| Watcher silent | Check toggles (`WELCOME_ENABLED`, `ENABLE_*`), review `/healthz` | Capture log snippet, open incident issue |
| Sheets outage | Switch to manual spreadsheet updates, disable writes via toggles | Note outage window, plan postmortem |
| Cache stale | Run `!rec refresh all`, confirm `[refresh]` completion | Monitor next scheduled refresh |

## Logging quick reference
- `[ops]` — deployment lifecycle, watchdog notices, and manual overrides.
- `[cron]` — cron job lifecycle (start/result/retry/summary, duration, target cache).
- `[watcher]` — watcher lifecycle messages (toggles, errors, thread IDs).
- `[command]` — execution context for CoreOps commands (caller, guild, result).

## Escalation ladder
1. Recruitment duty lead (Discord ping in #bot-production).
2. Platform on-call (Render access + Sheets owner).
3. Org admin for Google Workspace escalations.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
