# Watchers & Schedules — Phase 3b

## Overview
Watchers automate welcome and promo ticket hygiene. They load configuration and Sheets
references on startup and register only when toggles enable them.

## Load order
1. `shared.config` — env snapshot (IDs, toggles, sheet metadata).
2. `shared.runtime` — logging, scheduler, watchdog wiring.
3. `shared.sheets.core` — Google API client + worksheet cache.
4. `sheets.recruitment` / `sheets.onboarding` — TTL caches for clan data and templates.
5. Feature modules — watchers register event hooks and scheduled jobs.

_If steps 1–4 fail, abort boot. If a watcher fails to load, continue without it and emit a
single structured log._

## Data flows
- **Reads**: watchers consume clan tags, templates, and ticket rows via Sheets adapters.
- **Writes**: onboarding watchers write to `WelcomeTickets` / `PromoTickets` using bounded
  retry helpers that invalidate only the affected cache bucket.

## Caches & invalidation
- `shared.sheets.core` caches worksheet handles (no TTL).
- `sheets.recruitment` / `sheets.onboarding` keep TTL caches for values.
- `!reload` reloads config, clears TTL caches, and can optionally evict worksheet handles.
- Scheduled refresh (3× daily) clears TTL caches, then warms them.

## Toggles & roles
| Toggle | Purpose |
| --- | --- |
| `WELCOME_ENABLED` | Master enable for welcome command + watchers. |
| `ENABLE_WELCOME_WATCHER` | Registers welcome watcher hooks when true. |
| `ENABLE_PROMO_WATCHER` | Registers promo watcher hooks when true. |

Role gates come from `shared.coreops_rbac` using `ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`,
`RECRUITER_ROLE_IDS`, and `LEAD_ROLE_IDS`.

## Scheduler responsibilities
- Sheets refresh cycle (invalidate → warm → log).
- Daily recruiter digest distribution.
- Cleanup or hygiene jobs registered by watcher modules.

## Failure handling & health
- Read failure → serve stale cache (if present) and log error.
- Write failure → log structured error (ticket, tab, row, reason) and enqueue bounded
  retry.
- `/healthz` reports watcher toggle state, last refresh, and watchdog timers.
- `LOG_CHANNEL_ID` receives all watcher lifecycle logs (`[watcher]`).

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
