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
- **Discord Cog → CoreOps:** All commands funnel through the shared CoreOps cog. RBAC
  decisions happen before touching cache APIs.
- **Cache service:** Every cache interaction uses the public API (`get_snapshot`,
  `refresh_now`). Private module attributes remain internal to the service.
- **Google Sheets:** Recruitment and onboarding tabs are accessed asynchronously via the
  cached adapters. Preloader warms their handles and key buckets on startup.
- **Sheets access:** Async command handlers import `shared.sheets.async_facade`, which
  routes synchronous helpers through `asyncio.to_thread` so the event loop stays
  unblocked even on cache misses.
- **Preloader:** Runs automatically during boot, logging `[refresh] startup` entries for
  each bucket.
- **Scheduler:** Handles cron work including the 3-hour `bot_info` refresh, digest
  delivery, and template/watchers hygiene tasks.
- **Telemetry → Embed renderer:** Command responses pull structured telemetry and render
  embeds without timestamps; version metadata lives solely in the footer.
- **Runtime HTTP interface:** `/` returns the full status payload, `/ready` answers with
  `{ "ok": true }`, and `/health` + `/healthz` remain the long-form liveness endpoints
  with watchdog metadata.

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

Doc last updated: 2025-10-25 (v0.9.5)
