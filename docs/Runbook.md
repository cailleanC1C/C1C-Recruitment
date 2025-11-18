# Ops Runbook

Use this guide when operating the bot in production or test. It focuses on
observable actions: deploy/restart, health checks, cache hygiene, and what to do
when onboarding, welcome, recruitment, or placement flows misbehave.

## Lifecycle controls
- **Deploy / restart.** GitHub Actions builds the container and Render deploys the
  latest successful run per branch. To redeploy, push to the branch, wait for the
  workflow to finish, then trigger a manual deploy in Render if needed. Render
  restarts the process automatically when `/health` or the watchdog exit fails.
- **Manual restarts.** Run `!ops reload --reboot` in Discord to rebuild the
  config registry, flush caches, and restart the aiohttp server plus gateway
  session. Use this after updating Config tabs or environment variables.
- **Start/stop health.** Startup logs should include `web server listening` and
  `[watchdog] heartbeat` lines. Absence of either means the runtime did not reach
  `Runtime.start()`; inspect Render logs for import errors.

## Health & logging
- **HTTP probes.**
  - `/ready` turns `ok=true` once Discord connects and CoreOps finishes startup.
  - `/health` surfaces watchdog metrics plus component status (`runtime`,
    `discord`, `sheets`). A 503 indicates stalled heartbeats or a failed
    component.
  - `/healthz` is liveness only (process/heartbeat age check).
- **Discord diagnostics.** `!ops health` and `!ops digest` mirror the telemetry
  returned by `/health`, including cache age, next scheduled refresh, retries,
  and last actor.
- **Logs.** Runtime logs are JSON with `ts`, `level`, `logger`, `msg`, and
  `trace`. Use `trace` to correlate HTTP calls, refreshes, and command handlers.
  Healthy watchdog messages log at INFO; WARN/ERROR mean operator action.
- **Help diagnostics.** Temporarily set `HELP_DIAGNOSTICS=1` to post command
  discovery summaries into the log channel resolved by
  `resolve_ops_log_channel_id` for permission triage.

## Cache & scheduler operations
- **Startup preloader.** Each boot runs `refresh_now(name, actor="startup")` for
  every cache bucket. Expect `[refresh] startup bucket=<name>` logs followed by a
  single summary embed in the ops channel.
- **Manual refreshes.** `!ops refresh <bucket|all>` triggers the same API used by
  the scheduler. Buckets fail soft (stale data served) but log the error. The
  telemetry embed records `actor` so you can audit manual runs.
- **Reload vs refresh.** `!ops reload` rebuilds the config registry and TTL caches
  without restarting the process. Use it after changing sheet tab names or
  Config keys. `!ops reload --reboot` restarts after reload. `!ops refresh` keeps
  the runtime up and only touches cache data.
- **Scheduler cadence.** Cron jobs refresh recruitment caches (`clans`,
  `templates`, `clan_tags`), welcome templates, and sheet-based reports. Failed
  cron refreshes emit WARN logs and keep retry counters for follow-up.

## Feature toggles & config
- **Source of truth.** Feature toggles, admin/staff role IDs, sheet IDs, and
  module gates live in the Config worksheet tabs documented in
  [`docs/ops/Config.md`](Config.md). Do **not** edit environment variables to
  flip a feature unless the Config doc explicitly calls it out.
- **Toggling workflow.** Update the FeatureToggles tab, run `!ops reload`, then
  confirm via `!cfg feature_name` or by watching the module boot logs. Missing
  tabs or unrecognized toggles fail closed.

## Day-to-day procedures
### Onboarding & welcome tickets
1. Confirm the welcome watcher is enabled (`enable_welcome_hook`,
   `welcome_enabled`). Use `!ops health` to ensure watchers show as healthy.
2. If a ticket stalls, run `!ops onb check` (see `docs/modules/Onboarding.md` for the
   config/data layout) to
   validate the sheet. The `!onb resume` command can restore a recruit's wizard
   card directly in the thread.
3. Closing a ticket automatically reconciles clan availability; review the
   placement log in the ops channel for `result=ok`. Failures mention the admin
   roles listed in `ADMIN_ROLE_IDS`.

### Recruitment panels & reservations
1. `!clanmatch` and recruiter panel commands rely on the recruitment caches.
   After editing the sheet, run `!ops refresh clans templates` to pick up the
   changes and watch for `[refresh] trigger=manual` logs.
2. Reservations use `!reserve`, `!reservations`, and the recruiter control
   thread documented in [`modules/Placement.md`](modules/Placement.md).
   - Check the FeatureToggles keys `placement_reservations` and
     `placement_target_select` before enabling.
   - Use `!ops digest` to inspect availability columns (`AF/AH/AI`) and retries,
     and `!reservations <clan>` in the interact channel when you need a live
     roster of active holds.
   - Reminder and auto-release jobs post 🧭 logs (`reservation_reminder`,
     `reservations-autorelease`) around 12:00Z/18:00Z; if those disappear, verify
     the feature toggle and scheduler health.

### Watchers & keepalive
- [`Watchers.md`](Watchers.md) is the canonical source for watcher gating,
  scheduler cadences, watchdog thresholds, and keepalive expectations.
- Promo/welcome watchers are gated by sheet toggles (`enable_promo_watcher`,
  `enable_welcome_hook`). Disable the toggle first during incidents, then follow
  the escalation steps in `docs/ops/Watchers.md`.

## Maintenance cadence
- **Per deploy:** Verify `/ready`, `/health`, and `!ops digest` after redeploying.
  Ensure the help command lists all modules for the Admin audience.
- **Weekly:**
  - Run `!ops refresh all` during a quiet window to validate every cache bucket.
  - Review log volume for watchdog warnings and adjust `WATCHDOG_*` thresholds if
    Render restarts are too frequent.
  - Confirm the FeatureToggles sheet still lists every module expected in
    `docs/README.md`.
- **Monthly:**
  - Audit `config/bot_access_lists.json` via `!perm bot list --json` and compare
    against Discord channel reality.
  - Validate onboarding question tabs with `!ops onb check` plus a manual ticket
    walkthrough in the test guild.
  - Re-run the welcome template cache with `!welcome-refresh` to ensure new copy
    flows through the wizard.

## Reference map
- [`docs/README.md`](README.md) — which module owns each flow.
- [`docs/modules/CoreOps.md`](modules/CoreOps.md) — runtime contracts for schedulers, logging,
  and cache adapters.
- [`docs/Troubleshooting.md`](Troubleshooting.md) — deep-dive error lookup and
  mitigation tips.
- [`docs/ops/Watchers.md`](Watchers.md) — watcher gating and scheduler details.

Doc last updated: 2025-11-17 (v0.9.7)
