# Phase 3 Config & Env Guardrails Survey

## Unified `shared.config` flow (live bot)
- `shared.config` loads environment variables once at import via `_load_config()` / `reload_config()`, normalizing IDs, booleans, and schedules, and reuses cached values through helper getters.【F:shared/config.py†L176-L346】
- Boot-time defaults such as `LOG_CHANNEL_ID` fall back to the legacy production channel while permitting overrides through env. All getters reference the cached map rather than reading `os.environ` repeatedly.【F:shared/config.py†L181-L347】
- Runtime helpers in `config.runtime` provide consistent fallbacks (port, watchdog timings, prefixes) that `shared.config` reuses when env is absent or invalid.【F:config/runtime.py†L1-L108】【F:shared/config.py†L176-L288】
- `shared.config` is the sole config entrypoint for live modules: the bot entrypoint (`app.py`), runtime scaffolding, RBAC helpers, Ops cog, and onboarding watchers only import from this module.【F:app.py†L12-L99】【F:shared/runtime.py†L16-L310】【F:shared/coreops_rbac.py†L6-L63】【F:ops/ops.py†L6-L48】【F:onboarding/watcher_welcome.py†L7-L43】【F:onboarding/watcher_promo.py†L7-L43】

## Allow-list enforcement (`GUILD_IDS`)
- Live code gates startup and subsequent guild joins via `_enforce_guild_allow_list`, closing the bot if any connected guild ID is outside the configured allow-list and logging through the runtime log channel helper.【F:app.py†L56-L99】 
- Legacy Matchmaker and WelcomeCrew sources never referenced `GUILD_IDS`; no allow-list exists in those bots, so deployments historically relied on manual guild control rather than configuration.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2497-L2544】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L32-L92】

## `LOG_CHANNEL_ID` sourcing
- Live runtime pulls `LOG_CHANNEL_ID` from env (with the same legacy default channel) and routes all system notifications through `Runtime.send_log_message`, plus onboarding watcher toggles use it for disablement notices.【F:shared/config.py†L181-L347】【F:shared/runtime.py†L207-L270】【F:onboarding/watcher_welcome.py†L16-L43】【F:onboarding/watcher_promo.py†L16-L43】
- Matchmaker hard-codes the production log channel ID in source when instantiating the Welcome cog, overriding any env override. This conflicts with the new shared config expectation.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2497-L2523】
- WelcomeCrew continues to source the log channel (optional) from `LOG_CHANNEL_ID` env, aligning with the shared config contract.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L38-L83】

## Sheet ID & tab loading
- Live helpers read sheet IDs through the shared config (`RECRUITMENT_SHEET_ID`, `ONBOARDING_SHEET_ID`) and layer Sheet-specific defaults: recruitment defaults to `bot_info` / `WelcomeTemplates`, onboarding to `WelcomeTickets` / `PromoTickets` / `ClanList`, all overridable through config tabs.【F:shared/config.py†L186-L215】【F:sheets/recruitment.py†L1-L96】【F:sheets/onboarding.py†L1-L110】
- `shared.sheets.core` centralizes service-account handling, retries, and worksheet caching keyed by sheet ID + tab so both recruitment and onboarding modules reuse connections.【F:shared/sheets/core.py†L1-L96】
- Legacy Matchmaker expects `GOOGLE_SHEET_ID` + `WORKSHEET_NAME` for recruitment data and a separate `WELCOME_SHEET_TAB` for templates, re-opening the workbook for each call. WelcomeCrew reads `GSHEET_ID` with per-tab env overrides (Sheet1, Sheet4, clanlist).【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L64-L150】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2506-L2523】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L38-L118】
- The new recruitment bridge replaces the legacy Welcome cog’s `get_rows` with `sheets.recruitment.fetch_welcome_templates`, letting shared caching feed the existing async commands while aligning role gates with shared RBAC config.【F:recruitment/welcome.py†L1-L30】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py†L200-L245】

## Remaining AUDIT imports
- Ripgrep shows no runtime modules import from the `AUDIT/` tree; matches only appear inside audit documentation, so no legacy references leak into live code.【b5684a†L1-L88】

## Async + cached Sheets collision risks
- `shared.sheets.core` retries use blocking `time.sleep`, and all fetch helpers remain synchronous. When invoked from async tasks (e.g., watchers scheduled via `Runtime.schedule_at_times` or cog commands), these calls will block the event loop until gspread returns, similar to the legacy behavior we are attempting to improve.【F:shared/sheets/core.py†L1-L86】【F:shared/runtime.py†L273-L311】
- Recruitment and onboarding Sheet modules add their own TTL caches on top of `core`’s workbook cache, while the legacy Matchmaker cog also maintains an in-memory template cache. Coordinating refresh triggers (legacy commands vs. new scheduled jobs) will need explicit invalidation to avoid conflicting views of Sheet data.【F:sheets/recruitment.py†L1-L118】【F:sheets/onboarding.py†L1-L165】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py†L200-L245】
- Both legacy bots already cache rows (`get_rows` / `_cache_rows`, `_ws_cache`), so layering the shared caches without migrating those call sites risks duplicate cache warming on first access. Until watchers are rewritten to use async-aware fetchers, expect redundant gspread hits at startup or when manual reload commands bypass shared invalidation knobs.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L100-L154】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L115-L170】

## Live vs legacy config mismatches
- Live code standardizes IDs (`RECRUITMENT_SHEET_ID`, `ONBOARDING_SHEET_ID`, `RECRUITERS_THREAD_ID`, role sets) and enforces them via shared getters, whereas legacy modules rely on differently named env variables and sometimes reparse them manually (e.g., `ROLE_ID_RECRUITMENT_COORDINATOR`, sheet tab names).【F:shared/config.py†L186-L222】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L64-L123】
- The shared config assumes env-provided `GUILD_IDS` and log channel toggles, but legacy bots lack allow-list support and in Matchmaker’s case ship a hard-coded log channel. These inconsistencies must be resolved before the unified runtime can safely replace the old processes.【F:app.py†L56-L118】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2497-L2544】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L32-L92】

## Planning references
- Relates to #2, #14, #31, #37 (context only).

Doc last updated: 2025-10-15 (v0.9.5)
