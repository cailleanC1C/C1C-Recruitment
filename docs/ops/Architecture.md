# CoreOps Architecture — Phase 3 + 3b

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
- **Preloader:** Runs automatically during boot, logging `[refresh] startup` entries for
  each bucket.
- **Scheduler:** Handles cron work including the 3-hour `bot_info` refresh, digest
  delivery, and template/watchers hygiene tasks.
- **Telemetry → Embed renderer:** Command responses pull structured telemetry and render
  embeds without timestamps; version metadata lives solely in the footer.

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
