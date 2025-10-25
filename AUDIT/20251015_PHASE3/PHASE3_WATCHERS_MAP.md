# Phase 3 Discovery — Watchers & Role Gates Surfaces

## Overview
This note maps the Welcome/Promo watcher touch points in the live C1C runtime versus the audited legacy bots so the Sheet helpers can replace direct gspread usage.

## Live runtime (C1C-Recruitment)

### Extension wiring & watcher entry
- The shared runtime loads the core ops, recruitment search, recruitment welcome bridge, and both onboarding watcher modules during startup. The watchers are therefore extension `setup()` hooks rather than Discord event handlers today.【F:shared/runtime.py†L313-L333】
- Each watcher module currently short-circuits in `setup()` when either `WELCOME_ENABLED` or the watcher-specific toggle is false. When disabled it posts a notice to the configured log channel asynchronously; when enabled it only calls the onboarding shim (`ensure_loaded`) so the legacy cog can be attached later.【F:onboarding/watcher_welcome.py†L20-L47】【F:onboarding/watcher_promo.py†L20-L47】【F:onboarding/__init__.py†L8-L10】
- Because `ensure_loaded` is still a no-op placeholder, no watcher event listeners are registered yet—the Phase 3 work will need to import and bind the legacy handlers at this point.

### Configuration toggles & log channel sourcing
- `shared.config` hydrates `WELCOME_ENABLED`, `ENABLE_WELCOME_HOOK`, `ENABLE_PROMO_WATCHER`, `ENABLE_NOTIFY_FALLBACK`, and `LOG_CHANNEL_ID` from the environment snapshot. These values are available to the watcher modules through the accessor helpers the modules import.【F:shared/config.py†L200-L346】
- Runtime helpers use the same log channel ID when emitting scheduler or watchdog notifications (`Runtime.send_log_message`), so the watcher toggle announcements stay consistent with other bot diagnostics.【F:shared/runtime.py†L200-L333】【F:onboarding/watcher_welcome.py†L20-L47】

### Role gates
- Role sets (`ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`, `RECRUITER_ROLE_IDS`, `LEAD_ROLE_IDS`) are normalized in `shared.config` and exposed via `shared.coreops_rbac`. The helper checks merge Admin overrides with staff/recruiter/lead membership and are reused by CoreOps and recruitment features.【F:shared/config.py†L200-L346】【F:shared/coreops_rbac.py†L1-L112】
- The recruitment welcome bridge attaches Sheets-backed template lookup (`sheets.recruitment.fetch_welcome_templates`) to the legacy `welcome_cog` and restricts its commands to staff/admin role IDs pulled from those helpers, aligning the live permissions with the config file rather than raw env parsing.【F:recruitment/welcome.py†L15-L33】
- Recruitment loading is still a stub, so the legacy cog is only available once the Phase 3 loader is implemented.【F:recruitment/__init__.py†L8-L10】

### Background activity
- No watcher background loops run yet. The runtime scheduler exists (`Runtime.schedule`) and posts results to the log channel, but the onboarding watchers do not register tasks; Phase 3 will need to move the legacy scheduled refresh/watchdog loops into these helpers.【F:shared/runtime.py†L300-L333】

## Legacy WelcomeCrew (AUDIT/20251010_src/WC)

### Flags, toggles, and role inputs
- Environment parsing is performed via `env_bool` with explicit toggles for live watchers (`ENABLE_LIVE_WATCH`, `ENABLE_LIVE_WATCH_WELCOME`, `ENABLE_LIVE_WATCH_PROMO`), sheet scans, and notify fallbacks. Channel/role IDs are ingested directly from the environment, including `WELCOME_CHANNEL_ID`, `PROMO_CHANNEL_ID`, `NOTIFY_PING_ROLE_ID`, and `LOG_CHANNEL_ID`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L88】
- Watch-status tracking stores the toggle states and recent actions in an in-memory deque for `!watch_status`, mixing configuration (`ENABLE_LIVE_WATCH*`) with runtime log lines.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L689-L724】

### Event listeners & watcher flow
- Legacy watchers hook Discord events directly: socket/ready/connect/resumed events feed the watchdog timestamping, `on_thread_create` auto-joins welcome/promo threads, `on_message` performs close-detection/prompting, and `on_thread_update` finalizes tickets on archive/lock transitions.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1802】
- Close handling writes to Google Sheets via `_finalize_welcome` / `_finalize_promo`, which call `get_ws`, `upsert_*`, and rename threads before logging the action. These functions are invoked both from the message watcher and the archive watcher paths.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L859】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1800】

### Background tasks
- A scheduled refresh loop runs three times per day to reload clan tags and warm worksheet handles; it posts success notices to `LOG_CHANNEL_ID` and prints failures for watchdog diagnosis.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1540-L1610】
- The watchdog task (`@tasks.loop`) monitors gateway idleness and disconnect duration, exiting the process when zombie/disconnect heuristics trip. Startup wires it in `on_ready` and tracks disconnect timestamps in `on_disconnect`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1471】

### Notify/log routing
- `LOG_CHANNEL_ID` is also used by the refresh loop to report cache refreshes, while notify fallbacks (`ENABLE_NOTIFY_FALLBACK`, `NOTIFY_CHANNEL_ID`, `NOTIFY_PING_ROLE_ID`) mention staff when the bot cannot DM closers. These environment IDs are read once at import time.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L50-L87】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L726-L759】

## Legacy Matchmaker bridge (AUDIT/20251010_src/MM)
- The Matchmaker bot embeds the Welcome cog by instantiating `Welcome` with `WELCOME_ALLOWED_ROLES`, `WELCOME_GENERAL_CHANNEL_ID`, `WELCOME_ENABLED`, and a hard-coded `LOG_CHANNEL_ID`. It fetches Sheets data synchronously via `get_welcome_rows`, bypassing shared helpers, and primes `welcome_cog` once at import time.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2497-L2525】
- The legacy `welcome.py` cog handles Discord command gating internally, logging to the same `log_channel_id` and formatting templates with clan-role placeholders; Sheets writes still use direct gspread calls within the cog.【F:AUDIT/20251010_src/MM/welcome.py†L1-L120】

## Live vs. legacy gaps to close in Phase 3
- **Watcher registration** – Live code only exposes stub `setup()` hooks; the legacy implementation contains the concrete `on_message`/`on_thread_update` handlers and pending-state tracking that must be ported behind the shared watcher helpers.【F:onboarding/watcher_welcome.py†L41-L47】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1800】
- **Sheets access** – Legacy watchers issue `_run_blocking` gspread calls and in-function retries. Live modules should reroute these through the shared Sheets helpers to avoid blocking the event loop.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L859】
- **Toggles & role data** – Live config centralizes toggles/role sets and exposes them to multiple modules, while legacy code parses env vars ad-hoc (e.g., `WELCOME_ALLOWED_ROLES`). Phase 3 must map the legacy expectations to the shared config contract so watchers honour the same role gates without duplicating parsing logic.【F:shared/config.py†L200-L346】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2497-L2525】
- **Background loops** – Legacy scheduled refresh and watchdog loops run inside the WelcomeCrew script. These need equivalents under the shared runtime’s scheduler/watchdog utilities so cache refreshes and gateway health checks survive the migration.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1397-L1610】【F:shared/runtime.py†L300-L333】

## References to planning issues
Relates to tracking issues #20, #6, #2, and #11 per brief (no status changes performed here).
