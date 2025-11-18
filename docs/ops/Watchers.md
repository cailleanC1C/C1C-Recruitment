# Watchers & Scheduled Jobs

## Purpose
Watchers keep the recruitment runtime “always-on” by reacting to Discord events,
refreshing caches, and nudging Render so the container never idles. This single
source of truth covers every automation hook:

- **Event-driven watchers** listen to welcome/promo threads and infrastructure
  events, writing to Sheets and keeping permissions aligned.
- **Scheduled jobs** preload caches, post the Daily Recruiter Update, and surface
  health telemetry so command handlers always operate against fresh data.
- **Keepalive** pings the public route to prevent Render from hibernating,
  complementing the watchdog thresholds.

## Watcher & job inventory
### Event-driven watchers
| Name | Location | Trigger | Responsibilities | Logging | Feature toggles / config |
| --- | --- | --- | --- | --- | --- |
| **Welcome watcher** | `modules.onboarding.watcher_welcome.WelcomeWatcher` | Ticket Tool greeting, 🎫 emoji, manual ticket close, Ticket Tool close message | Posts/reposts the onboarding questionnaire, records answers into the onboarding Sheet, prompts for clan confirmation, reconciles reservations, and renames threads on closure. Also emits the onboarding lifecycle notice during startup. | `c1c.onboarding.welcome_watcher` logger with `[welcome_watcher] …` and `[watcher\|lifecycle]` startup messages routed to `LOG_CHANNEL_ID`. | Requires `WELCOME_CHANNEL_ID`, `WELCOME_TICKETS_TAB`, and FeatureToggles keys `welcome_enabled`, `enable_welcome_hook`, `welcome_dialog`, and `recruitment_welcome`. | 
| **Promo watcher** | `modules.onboarding.watcher_promo.PromoWatcher` | Promo ticket close messages | Mirrors the welcome watcher for promo threads by logging closures to the promo Sheet tab and posting placement summaries. | `c1c.onboarding.promo_watcher` logger with `[promo_watcher] …` messages in the ops log channel. | Requires `PROMO_CHANNEL_ID` plus FeatureToggles keys `welcome_enabled`, `welcome_dialog`, and `enable_promo_watcher`. |
| **Bot permission watcher** | `modules.ops.watchers_permissions.BotPermissionWatcher` | `on_guild_channel_create` and `on_guild_channel_update` (category move) | Automatically reapplies the bot-role overwrite profile when new channels are created or moved under an allowed category, matching the behaviour of `!perm bot sync`. | Posts `🔐 Bot permissions applied automatically …` via `modules.common.runtime.send_log_message`; WARN lines log as `Watcher failed to update overwrites` when Discord rejects the write. | Respects `config/bot_access_lists.json` and the persisted `threads_default` option managed by the `!perm bot` command group. |

### Scheduled jobs & loops
| Job | Module | Cadence | Responsibilities | Logging | Config / toggles |
| --- | --- | --- | --- | --- | --- |
| **Cache refresh – clans** | `modules.common.runtime.scheduler` (`shared.sheets.recruitment`) | Every 3 h | Clears the `clans` bucket and reloads recruitment roster data so `!clanmatch` and placements operate on fresh availability. | `[cache] bucket=clans` embeds plus structured console logs (success/error) routed to `LOG_CHANNEL_ID`. | `CLANS_TAB` sheet key; cadence is fixed in code today. |
| **Cache refresh – templates** | Same scheduler | Every 7 d | Refreshes welcome/promo template content, ensuring watchers post the latest copy. | `[cache] bucket=templates` logs. | `WELCOME_TEMPLATES_TAB` sheet key. |
| **Cache refresh – clan_tags** | Same scheduler | Every 7 d | Refreshes the clan tag autocomplete cache used in the watcher dropdowns. | `[cache] bucket=clan_tags` logs. | `CLAN_TAGS_CACHE_TTL_SEC` controls TTL; cadence fixed. |
| **Onboarding questions refresh** | `shared.sheets.onboarding` warmers | Weekly | Reloads onboarding question forms to match the latest Config worksheet. | `[cache] bucket=onboarding_questions` (startup + scheduler) with `actor=startup` or `actor=scheduler`. | Requires `ONBOARDING_TAB` and FeatureToggles enabling onboarding modules. |
| **Daily Recruiter Update** | `modules.recruitment.reporting.daily_recruiter_update.scheduler_daily_recruiter_update` | Once per day at `REPORT_DAILY_POST_TIME` (UTC) | Posts the recruiter digest embed summarizing placements, queues, and cache freshness into `REPORT_RECRUITERS_DEST_ID`. | Structured console logs plus the Discord embed; scheduler start/stop events log via `daily_recruiter_update` helpers. | `REPORT_DAILY_POST_TIME`, `REPORT_RECRUITERS_DEST_ID`, and the `recruitment_reports` feature toggle. |

## Keepalive behaviour
Render tears down idle services unless they see periodic traffic. The runtime
keeps the bot “warm” in two layers:

1. **HTTP keepalive task.** `modules.common.keepalive.ensure_started()` launches a
   background task that `GET`s the configured keepalive route.
   - **Route.** `GET /keepalive` handled by the aiohttp server. Override the path
     with `KEEPALIVE_PATH`; defaults to `/keepalive`.
   - **URL resolution order.** `KEEPALIVE_URL` → `RENDER_EXTERNAL_URL` +
     `KEEPALIVE_PATH` → `http://127.0.0.1:{PORT}/keepalive` for local dev.
   - **Interval.** `KEEPALIVE_INTERVAL` seconds (minimum 60, default 300). The
     deprecated `KEEPALIVE_INTERVAL_SEC` env overrides the watchdog cadence and
     logs a warning via `config/runtime.py` for backward compatibility.
   - **Logs.** Expect `keepalive:task_started` once and recurring
     `keepalive:ping_ok` (or `keepalive:ping_fail`) lines in the bot logs.
2. **Watchdog timers.** The Discord watchdog runs on `WATCHDOG_CHECK_SEC` (360 s
   prod / 60 s non-prod) and trips after `WATCHDOG_STALL_SEC` (`check*3+30`).
   `WATCHDOG_DISCONNECT_GRACE_SEC` covers the gateway reconnect window. These
   timers exit the process when heartbeats stall so Render can restart it.

## Operations
- **Verify watcher health.**
  - Run `!ops health` or `!ops digest` to inspect cache timestamps, next refresh
    times, and watcher toggle states (mirrors `/health`).
  - Inspect `[watcher|lifecycle] …` startup logs in `LOG_CHANNEL_ID` after each
    deploy; missing lifecycle lines mean a watcher failed to register.
  - For promo/welcome incidents, disable the relevant FeatureToggles entry,
    restart via `!ops reload --reboot`, then document the change in this file.
- **Diagnose scheduler issues.** Look for `[cache] bucket=… result=error` logs or
  WARN-level entries in Render. Manual `!ops refresh <bucket>` invokes the same
  warmers and records `actor=manual` for audits.
- **Keepalive triage.** Absence of `keepalive:` logs means the ready hook never
  called `ensure_started()`; confirm `Runtime.start()` reached completion.
  Non-200 responses usually mean `KEEPALIVE_URL` points to the wrong host.
- **Daily Recruiter Update.** Use `!ops health` to check the `recruitment_reports`
  flag and verify that `scheduler_daily_recruiter_update` is running. The
  scheduler can be restarted via `modules.recruitment.reporting.daily_recruiter_update.ensure_scheduler_started()`.
- **Permission watcher.** When new channels lack overwrites, run `!perm bot sync
  --dry false` to remediate and review `Watcher failed to update overwrites`
  logs for Discord-side errors (missing permissions, manual denies, etc.).

## Related docs
- [`docs/Architecture.md`](../Architecture.md) — runtime surfaces and scheduler
  relationships.
- [`docs/Runbook.md`](../Runbook.md) — operational procedures that call into
  these watchers and schedulers.
- [`docs/ops/Config.md`](Config.md) — environment keys, FeatureToggles, and sheet
  tabs referenced above.
- [`docs/modules/CoreOps.md`](../modules/CoreOps.md) — runtime lifecycle,
  scheduler wiring, and watchdog contracts.
- [`docs/modules/`](../modules) — module owners for the watchers listed here.

Doc last updated: 2025-11-17 (v0.9.7)
