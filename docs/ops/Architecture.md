# CoreOps Architecture

```
Discord Cog ─┬─> CoreOps command handlers ──> Cache Service ──> Google Sheets
             │                               │                    (Recruitment &
             │                               │                     Onboarding)
             │                               │
             └─> Telemetry bus ──> Embed Renderer ──> Discord embeds

Preloader ──> Cache Service.refresh_now(name, actor="startup")
             │
             └─> Scheduler ──> bot_info refresh (every 3 h)

User (any tier) ──> Discord Cog ──> CoreOps telemetry fetch ──> Embed Renderer
                                        │
                                        └─> Public telemetry helpers only
```

### Flow notes
- **Diagram legend:** CoreOps command handlers (purple) orchestrate Shared services (blue),
  which expose async facades to feature modules (green).
- **Discord Cog → CoreOps:** All commands funnel through the shared CoreOps cog. RBAC
  decisions happen before touching cache APIs.
- **Cache service:** Every cache interaction uses the public API (`get_snapshot`,
  `refresh_now`). Private module attributes remain internal to the service.
- **Google Sheets:** Recruitment and onboarding tabs are accessed asynchronously via the
  cached adapters. Preloader warms their handles and key buckets on startup.
- **Sheets access:** Async command handlers import `shared.sheets.async_facade`, which
  routes synchronous helpers through `asyncio.to_thread` so the event loop stays
  unblocked even on cache misses.
- **Health system:** `shared.health` tracks component readiness; the runtime flips
  statuses for `/ready` and `/health` whenever Discord or the HTTP server changes state.
- **Preloader:** Runs automatically during boot, logging `[refresh] startup` entries for
  each bucket.
- **Scheduler:** Handles cron work including the 3-hour `bot_info` refresh, digest
  delivery, and template/watchers hygiene tasks.
- **Telemetry → Embed renderer:** Command responses pull structured telemetry and render
  embeds without timestamps; version metadata lives solely in the footer.
- **Runtime HTTP interface:** `/` returns the status payload and echoes the request
  trace id, `/ready` exposes the readiness gate with component details, `/health`
  combines the watchdog metrics with the component map, and `/healthz` remains the
  bare liveness probe.
- **Logging & observability:** All runtime logs emit JSON via
  `shared.logging.structured.JsonFormatter` with
  `ts`,`level`,`logger`,`msg`,`trace`,`env`,`bot` plus contextual extras. HTTP
  access logs are emitted under the canonical `aiohttp.access` logger with
  `path`,`method`,`status`, and latency (`ms`).
- **Request tracing:** Every web request receives a UUIDv4 trace id that flows
  through the log context, `/` response payload, and the `X-Trace-Id` response
  header for quick correlation.

### Module topology
- CoreOps now lives in `packages/c1c-coreops/src/c1c_coreops/`.
- `shared/coreops_*` modules are deprecated shims re-exporting the new package for one release.

### Feature gating at load
- **Module wiring:** Feature modules call `modules.common.feature_flags.is_enabled(<key>)` during boot.
  Disabled toggles block command registration and watcher wiring; the bot logs the skip
  and continues.
- **Backbone always-on:** Scheduler, cache service, health probes, RBAC helpers, and the
  watchdog never consult feature toggles. They remain active even when every feature key
  fails.
- **Fail-closed behavior:** Missing worksheet, headers, or row values evaluate to
  `False`. The runtime emits a single admin-ping warning per issue in the log channel and
  leaves the module offline until the Sheet is fixed and refreshed.
- **Feature map:**
  - `member_panel` — member view of recruitment roster/search panels.
  - `recruiter_panel` — recruiter dashboard, match queue, and escalations.
  - `recruitment_welcome` — welcome command plus onboarding listeners.
  - `recruitment_reports` — daily recruiter digest watcher and embeds.
  - `placement_target_select` — placement targeting picker inside panels.
  - `placement_reservations` — reservation holds and release workflow.

Doc last updated: 2025-10-26 (v0.9.6)
