# CoreOps Explainer

CoreOps is the runtime spine of this repository. It owns the Discord cog that
loads first, the scheduler, Sheets adapters, and the structured logging/health
surfaces that every functional module relies on. For deeper implementation
notes, see [`docs/modules/CoreOps-Development.md`](CoreOps-Development.md).

## Responsibilities
- **Command routing & RBAC.** The CoreOps cog in `packages/c1c-coreops` registers
  the `!ops` command tree, admin bang shortcuts, and the permission decorators
  shared by feature modules. Every Discord command passes through CoreOps before
  reaching the module handler.
- **Lifecycle hooks.** Startup, reload, refresh, and watchdog events emit
  `[watcher|lifecycle]` log lines and send status embeds to the ops channel.
  `!ops reload` rebuilds the config registry and TTL caches; `!ops refresh` calls
  the cache façade; `!ops reload --reboot` restarts the runtime after reload.
- **Scheduler.** Handles cache refresh jobs (`clans`, `templates`, `clan_tags`,
  `welcome_templates`, reservations) plus cron-based reports (daily recruiter
  update). Scheduler runs inside the CoreOps runtime thread and records telemetry
  per job.
- **Sheets façade.** Modules import `shared.sheets.async_facade`. The façade
  serializes cache calls, routes synchronous helpers through
  `asyncio.to_thread`, and raises module-friendly exceptions so feature code does
  not need to understand the lower-level adapters.
- **Health & logging.** CoreOps configures the aiohttp health server and the JSON
  logging formatter (`shared.logging.structured.JsonFormatter`). Every HTTP
  request receives a `trace` id echoed in the response headers.

## Integration points
- **Modules.** Modules expose cogs in `cogs/` that register their commands. They
  resolve config, Sheets data, and feature toggles through CoreOps helpers such
  as `shared.config.registry`, `modules.common.feature_flags`, and the cache API
  (`refresh_now`, `get_snapshot`). Deep dives live under `docs/modules/`.
- **Sheets & config registry.** CoreOps caches sheet tabs using bucket metadata
  stored in the Config worksheet (`docs/ops/Config.md`). Reloading the registry
  clears TTL caches and re-reads tab definitions before modules resume work.
- **Telemetry.** Operational embeds (`!ops health`, `!ops digest`, `!ops checksheet`)
  read only the public telemetry payloads produced by CoreOps. No module is
  allowed to import private cache internals.

## Invariants
- All CoreOps code lives in `packages/c1c-coreops`. CI fails if CoreOps helpers
  appear elsewhere.
- Cache access must go through the async façade; direct adapter imports are
  disallowed.
- Feature toggles default to disabled when missing or malformed.
- Watchdog exits should be the only reason the process stops unexpectedly; any
  other crash must be treated as a regression.

## Module expectations
- Modules must log via the structured logger and include the active `trace` when
  they respond to HTTP requests or refresh caches.
- Long-running handlers must release the event loop by offloading blocking work
  to `asyncio.to_thread` or background tasks.
- Modules should record the invoking actor in telemetry when they trigger cache
  refreshes or reconciliations so `!ops digest` remains auditable.

Doc last updated: 2025-11-17 (v0.9.8.2)
