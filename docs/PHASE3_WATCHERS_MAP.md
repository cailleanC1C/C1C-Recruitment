# Phase 3 Discovery — Watchers & Role Gates Surfaces

## Runtime wiring (current repo)
- The unified runtime loads watcher modules alongside recruitment features via `BotRuntime.load_extensions`, ensuring both welcome and promo entry points run in the shared bot process.【F:shared/runtime.py†L313-L333】
- Each onboarding watcher module gates its `setup` on the recruitment master toggle (`WELCOME_ENABLED`) plus its own flag, then calls `ensure_loaded` to bridge into the legacy bot once sheet helpers land. Disabled states are announced via the log channel using `_announce_disabled`, which schedules a background send on the bot loop.【F:onboarding/watcher_welcome.py†L9-L47】【F:onboarding/watcher_promo.py†L9-L47】
- `onboarding.ensure_loaded` is currently a no-op shim, highlighting that legacy WelcomeCrew wiring has not been pulled into the live runtime yet.【F:onboarding/__init__.py†L1-L10】

## Configuration flags & env toggles
- Environment loading centralizes watcher toggles: `WELCOME_ENABLED`, `ENABLE_WELCOME_WATCHER`, `ENABLE_PROMO_WATCHER`, and `ENABLE_NOTIFY_FALLBACK` are parsed into the shared config snapshot alongside channel IDs, sheet IDs, and watchdog settings.【F:shared/config.py†L163-L205】
- Accessors expose these toggles and associated role/channel identifiers for downstream consumers, keeping the new runtime aligned with the legacy env contract.【F:shared/config.py†L384-L460】
- The legacy Matchmaker bot read `WELCOME_ENABLED` directly from `os.environ`, defaulting to enabled and wiring welcome command role gates via `WELCOME_ALLOWED_ROLES`. This highlights the need to redirect those reads through shared config helpers once watchers migrate fully.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2498-L2523】

## Role-gate helpers
- `shared.coreops_rbac` re-exposes admin/staff/recruiter/lead role sets from config and provides predicates (e.g., `is_staff_member`, `is_recruiter`) that mirror the legacy gating behavior while tolerating malformed IDs.【F:shared/coreops_rbac.py†L1-L112】
- Legacy WelcomeCrew used notification-specific roles (`NOTIFY_PING_ROLE_ID`) resolved from the environment for fallback pings when prompts could not be delivered in-thread, reinforcing the need to preserve those IDs in the migration.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L70-L88】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L726-L804】

## Logging sinks
- The shared config sets a default `LOG_CHANNEL_ID` (`#bot-production`) but allows overrides via environment, and runtime helpers will fetch/send to that channel for watcher status notifications and scheduled task results.【F:shared/config.py†L158-L205】【F:shared/runtime.py†L207-L225】
- The new watcher stubs reuse this log sink to announce when toggles disable a watcher, matching the behavior expected from WelcomeCrew’s `LOG_CHANNEL_ID` refresh pings.【F:onboarding/watcher_welcome.py†L20-L43】【F:onboarding/watcher_promo.py†L20-L43】
- Legacy WelcomeCrew also used `LOG_CHANNEL_ID` when scheduled refreshes completed, posting human-readable timestamps after cache reloads if the channel was configured.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L47-L66】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1538-L1605】

## Event entry points & background tasks (legacy WelcomeCrew)
- Discord listeners defined in `bot_welcomecrew.py` cover watcher lifecycle: `on_thread_create` auto-joins new threads, `on_message` handles close markers/tag ingestion, and `on_thread_update` finalizes archived threads or clears pending prompts.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1620-L1760】
- Watcher behavior is governed by env toggles (`ENABLE_LIVE_WATCH`, `ENABLE_LIVE_WATCH_WELCOME`, `ENABLE_LIVE_WATCH_PROMO`) declared alongside other feature flags at module import time.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L55-L87】
- Closing flows call `_finalize_welcome` / `_finalize_promo`, which rename threads, upsert rows to Sheets via `_run_blocking`, and log watcher actions for `!watch_status`. Missing tags trigger dropdown prompts or fallback channel notifications using the configured role/channel IDs.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L720-L839】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1731】
- Background tasks spawned by the legacy watcher include the 3×/day `scheduled_refresh_loop` (`bot.loop.create_task` from `on_ready`) for clan tag caching, the watchdog loop (`@tasks.loop`) that restarts the process on gateway stalls, and the startup webserver task used for health probes.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1500】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1500-L1595】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1794-L1810】

## Live vs. legacy wiring gaps
| Area | Current unified runtime | Legacy WelcomeCrew |
| --- | --- | --- |
| Watcher setup | Stubs ensure toggles respected and legacy loader called, but no event handlers or sheet writes are active yet.【F:onboarding/watcher_welcome.py†L41-L47】【F:onboarding/__init__.py†L1-L10】 | Full Discord event listeners drive live thread monitoring, tag prompting, and sheet writes on close events.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1620-L1788】 |
| Config consumption | Uses shared config snapshot for toggles, role IDs, and log channels, allowing centralized refresh/reload semantics.【F:shared/config.py†L163-L205】【F:shared/coreops_rbac.py†L47-L112】 | Each bot reads environment variables directly at import time (e.g., `WELCOME_ENABLED`, `LOG_CHANNEL_ID`, notification IDs), duplicating parsing logic.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2498-L2523】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L88】 |
| Logging | Unified `send_log_message` helper routes async notifications to the configured log channel and is reused by watchers when disabled.【F:shared/runtime.py†L207-L225】【F:onboarding/watcher_promo.py†L20-L43】 | Refresh pings and action logs use hard-coded or env-resolved channel IDs within the watcher module itself.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L47-L66】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1538-L1605】 |
| Background scheduling | Scheduler API exists in runtime, but watcher tasks are TODOs until sheet-backed flows migrate.【F:onboarding/watcher_welcome.py†L41-L47】【F:shared/runtime.py†L295-L333】 | Watchers bootstrap refresh loops, watchdog monitoring, and health server tasks directly via `bot.loop.create_task` and `@tasks.loop`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1500】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1794-L1810】 |

## Key follow-ups for Phase 3
1. Replace the `ensure_loaded` shim with concrete watcher adapters that call into shared sheet helpers, mirroring legacy finalization without blocking the event loop.【F:onboarding/__init__.py†L1-L10】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L720-L839】
2. Route role checks and notification fallbacks through `shared.coreops_rbac` / config helpers so legacy `NOTIFY_*` semantics survive the migration.【F:shared/coreops_rbac.py†L47-L112】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L726-L804】
3. Port scheduled refresh + watchdog responsibilities into the shared runtime scheduler to maintain cache freshness and gateway self-healing once watchers move over.【F:shared/runtime.py†L295-L333】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1500】
