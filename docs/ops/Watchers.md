# Watchers & Schedules — Phase 3b

## Overview
Watchers coordinate Discord-side automation for recruitment and onboarding. They load
configuration, warm Sheets caches, then register whichever listeners and cron jobs are
enabled for the deployment.

## Terminology (important)
- **Watcher** → *event-driven listener* registered on the Discord gateway. These respond
  immediately to welcome/promo activity and log using the `[watcher]` prefix.
- **Cron** → *scheduled job* triggered by the runtime scheduler. Cron runs are logged with
  the `[cron]` prefix (start/result/retry/summary).
- Legacy environment keys ending in `_WATCHER` still work but are **deprecated**. Prefer
  the new `*_LISTENERS` and `CRON_*` keys documented in [`Config.md`](Config.md).

## Load order
1. `shared.config` — env snapshot (IDs, toggles, sheet metadata).
2. `modules.common.runtime` — logging, scheduler, watchdog wiring.
3. `shared.sheets.core` — Google API client + worksheet cache.
4. `shared.sheets.recruitment` / `shared.sheets.onboarding` — TTL caches for clan data and templates.
5. Feature modules — watchers register event hooks and cron jobs based on toggles.

_If steps 1–4 fail, abort boot. If a watcher fails to load, continue without it and emit a
single structured log._

## Current Watchers (event listeners)
- **Welcome listeners** (`ENABLE_WELCOME_LISTENERS`) — greet new members, open tickets, and
  sync sheet rows. They now resolve channel, thread, and role targets from the shared
  config registry — no hard-coded IDs remain.
- **Promo listeners** (`ENABLE_PROMO_LISTENERS`) — track promo requests, tag recruiters, and
  update onboarding tabs. Targets load from the same registry to maintain parity between
  environments.

Watchers read clan tags, templates, and ticket rows via the Sheets adapters listed above.
Writes go back to `WelcomeTickets` / `PromoTickets` using bounded retry helpers that
invalidate only the affected cache bucket. Role gates come from
`shared.coreops_rbac` (`ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`, `RECRUITER_ROLE_IDS`,
`LEAD_ROLE_IDS`).

## Current Cron Jobs (scheduled)
- **Clan tag refresh** (`CRON_REFRESH_CLAN_TAGS`, default 15m) — invalidates and warms the
  clan tag cache.
- **Sheets sync** (`CRON_REFRESH_SHEETS`, default 30m) — reconciles Sheets metadata and logs
  durations.
- **Cache warmers** (`CRON_REFRESH_CACHE`, default 60m) — sweeps remaining caches and writes
  a daily roll-up summary to `[cron]`.
- **`bot_info` telemetry refresh** (`cron` every 3 h) — scheduler triggers
  `refresh_now("bot_info", actor="cron")`; completion logs post a success/failure summary
  to the ops channel.
- **Recruiter digest** — loads only when `modules.common.feature_flags.is_enabled("recruitment_reports")`
  evaluates `True`. The digest cron posts nightly summaries; when the toggle is off the
  scheduler skips registration. Welcome and promo watchers remain controlled by their
  `_LISTENERS` environment toggles and ignore feature flags.

Cron jobs run even if corresponding listeners are disabled (for example, refresh cycles can
stay active while promo listeners are paused).

## Caches & invalidation
- `shared.sheets.core` caches worksheet handles (no TTL).
- `shared.sheets.recruitment` / `shared.sheets.onboarding` keep TTL caches for values.
- `!reload` reloads config, clears TTL caches, and can optionally evict worksheet handles.
- Cron refreshes clear TTL caches before warming them; manual `!rec refresh` commands share
  the same helpers.

## Scheduler responsibilities
- Dispatch cron jobs on their configured cadence and log `[cron start]`, `[cron result]`,
  `[cron retry]`, and `[cron summary]` events.
- Deliver the daily recruiter digest.
- Register cleanup or hygiene jobs supplied by watcher modules.

## Failure handling & health
- Read failure → serve stale cache (if present) and log error.
- Write failure → log structured error (ticket, tab, row, reason) and enqueue bounded
  retry.
- `/healthz` reports watcher toggle state, last cron run, and watchdog timers.
- `LOG_CHANNEL_ID` receives all watcher lifecycle logs (`[watcher]`) plus cron notices
  (`[cron]`).

---

_Doc last updated: 2025-10-22 (v0.9.5 modules-first update)_
