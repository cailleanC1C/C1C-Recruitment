# Watchers & Schedules

## Overview
Watchers coordinate Discord-side automation for recruitment and onboarding. They resolve
configuration from Sheets, register their Discord listeners, and hand cache warm-up to the
shared scheduler. The current release ships two event listeners (welcome/promo thread
closures) and one scheduler that refreshes the Sheets caches.

## Terminology (important)
- **Watcher** → *event-driven listener* registered on the Discord gateway. These respond
  to welcome/promo thread updates and log using prefixes such as `[welcome_watcher]` and
  `[promo_watcher]`.
- **Lifecycle** → CoreOps runtime notices (startup, reload, manual refresh). They emit
  `[watcher|lifecycle]` for this release and will drop back to `[lifecycle]` next cycle.
- **Cron** → *scheduled job* triggered by the runtime scheduler. Cache refresh runs are
  logged with the `[cache]` prefix (bucket name, duration, retries, result).
- Feature toggles `welcome_enabled`, `enable_welcome_hook`, and
  `enable_promo_watcher` live in the recruitment Sheet `FeatureToggles` worksheet.
  See [`Config.md`](Config.md#feature-toggles-worksheet) for worksheet contract and defaults.

## Load order
1. `shared.config` — env snapshot (IDs, toggles, sheet metadata).
2. `modules.common.runtime` — logging, scheduler, watchdog wiring.
3. `shared.sheets.core` — Google API client + worksheet cache.
4. `shared.sheets.recruitment` / `shared.sheets.onboarding` — TTL caches for clan data and templates exposed through the async facade.
5. Feature modules — onboarding watchers and cache scheduler register based on the active toggles.

_If steps 1–4 fail, abort boot. If a watcher fails to load, continue without it and emit a
single structured log._

## Current Watchers (event listeners)
- **Welcome watcher** (`welcome_enabled` + `enable_welcome_hook`) — listens for welcome
  thread closures, appends a row to the configured Sheet tab, and logs the result via
  `[welcome_watcher]` messages.
- **Promo watcher** (`welcome_enabled` + `enable_promo_watcher`) — mirrors the welcome flow
  for promo threads, writing to the promo tab and logging as `[promo_watcher]`.

Both listeners rely on the onboarding Sheet adapters and reuse the bounded retry helpers in
`shared.sheets.async_core`. Failures reset their cached worksheet handles so the next event
retries with a fresh connection.

## Current Cron Jobs (scheduled)
- **`clans` refresh** — every 3 h (`cadence_label: 3h`). Warms the recruitment roster cache.
- **`templates` refresh** — every 7 d (`cadence_label: 7d`). Warms cached welcome templates.
- **`clan_tags` refresh** — every 7 d (`cadence_label: 7d`). Warms the tag autocomplete cache.

All jobs post `[cache]` summaries to the ops channel via `modules.common.runtime.send_log_message`.

## Caches & invalidation
- `shared.sheets.core` caches worksheet handles (no TTL).
- `shared.sheets.recruitment` / `shared.sheets.onboarding` keep TTL caches for values.
- `!reload` reloads config, clears TTL caches, and can optionally evict worksheet handles.
- Cron refreshes clear TTL caches before warming them; manual `!rec refresh` commands share
  the same helpers.

## Scheduler responsibilities
- Ensure cache buckets are registered (`ensure_cache_registration`).
- Register cache refresh jobs for `clans`, `templates`, and `clan_tags` with their configured cadences.
- Emit `[cache]` summaries to the ops channel for both success and failure cases.

## Failure handling & health
- Watcher read/write failure → log a structured warning (thread, tab, reason) and retry on the next event.
- Cache refresh failure → `[cache]` summary includes `err=...`; manual refresh commands remain available.
- `/healthz` reports watchdog metrics and cache timestamps; `!rec config` surfaces the active watcher toggles.
- `LOG_CHANNEL_ID` receives lifecycle notices plus watcher (`[welcome_watcher]`, `[promo_watcher]`) and `[cache]` refresh messages.

Doc last updated: 2025-10-26 (v0.9.6)
