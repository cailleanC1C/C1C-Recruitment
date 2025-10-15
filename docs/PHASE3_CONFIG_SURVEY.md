# Phase 3 Discovery — Config & Env Guardrails

## 1. Shared configuration loading in live code
- `shared.config` builds a snapshot once at import time, using helpers from `config.runtime` plus raw environment values for IDs, sheet keys, schedules, and toggles, then caches the result in `_CONFIG` via `reload_config()`.【F:shared/config.py†L158-L227】
- Default redaction metadata and the hard-coded `_DEFAULT_LOG_CHANNEL_ID` (1415330837968191629) remain in place for when `LOG_CHANNEL_ID` is unset; every getter reads from the cached snapshot so runtime modules never touch `os.environ` directly.【F:shared/config.py†L56-L206】【F:shared/config.py†L272-L320】
- `app.CONFIG_META` advertises that configuration came from `shared.config`, and `CFG = get_config_snapshot()` exposes the cached map for diagnostics without rereading the environment.【F:app.py†L234-L241】

### 1.1 Exposure across modules
- The Discord runtime hands `Runtime.send_log_message` the shared log channel ID each time it posts, re-fetching the configured channel if necessary before emitting a message.【F:shared/runtime.py†L207-L225】
- CoreOps RBAC bridges the cached role ID sets to Discord objects, ensuring numeric filtering aligns with the new snapshot.【F:shared/coreops_rbac.py†L15-L112】
- Operational commands use the shared snapshot to summarise allow-lists and sheet IDs, proving the getters are wired end-to-end.【F:ops/ops.py†L7-L52】

## 2. Guardrail enforcement (live)

### 2.1 Guild allow-list
- `_enforce_guild_allow_list` reads `GUILD_IDS` from `shared.config`, logs when the set is empty, and shuts the bot down if it detects a foreign guild during ready checks or new guild joins.【F:app.py†L56-L164】
- The getter accepts sets, lists, or tuples from `_CONFIG`, falling back to "allow all" when the list is empty, mirroring legacy permissiveness until IDs are supplied.【F:shared/config.py†L283-L306】

### 2.2 Log channel sourcing
- `LOG_CHANNEL_ID` resolves to the first integer found in the environment and otherwise falls back to `_DEFAULT_LOG_CHANNEL_ID`, matching the legacy hard-coded channel but allowing override via env.【F:shared/config.py†L163-L206】
- Runtime notifications and onboarding watcher toggles both respect the shared getter, so disabling or rerouting the log sink is centralised.【F:shared/runtime.py†L207-L225】【F:onboarding/watcher_welcome.py†L9-L47】

## 3. Google Sheets configuration paths

### 3.1 Live modules
- The shared config captures `RECRUITMENT_SHEET_ID` and `ONBOARDING_SHEET_ID`, while the Sheets helper falls back to `GOOGLE_SHEET_ID`/`GSHEET_ID` when callers omit an explicit key. Worksheet handles are cached per `(sheet_id, tab)` pair with retry/backoff wrappers around gspread calls.【F:shared/config.py†L168-L206】【F:shared/sheets/core.py†L1-L128】

### 3.2 Legacy Matchmaker (AUDIT)
- Legacy code reads `GOOGLE_SHEET_ID` and `WORKSHEET_NAME` directly, builds its own cache, and exposes a bespoke `get_welcome_rows()` that hits a `WELCOME_SHEET_TAB` within the same spreadsheet, bypassing any shared retry helpers.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L149】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2523】

### 3.3 Legacy WelcomeCrew (AUDIT)
- The watcher loads `GSHEET_ID` alongside sheet-specific names (`SHEET1_NAME`, `SHEET4_NAME`, `CLANLIST_TAB_NAME`) and manages its own worksheet cache and throttling, including notify-channel fallbacks tied to `LOG_CHANNEL_ID` and refresh loops that post when configured.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L137】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1503-L1613】

### 3.4 Tab references by environment
- Live code currently exposes IDs but defers to future modules for tab names; legacy Matchmaker expects `bot_info` plus `WelcomeTemplates`, while WelcomeCrew enforces `Sheet1`, `Sheet4`, and a clanlist tab with configurable column indices.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L149】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L41-L137】

## 4. AUDIT import status
- A repo-wide search shows no runtime modules import from `AUDIT/…`; only documentation references remain, so live code is clean of legacy direct imports.【2f1a03†L1-L114】

## 5. Collisions to expect with an async + cached Sheets layer
- The shared Sheets helper caches workbook and worksheet handles globally and retries operations with `time.sleep`, which will block the event loop when called from async watchers unless wrapped in executors.【F:shared/sheets/core.py†L24-L128】
- Legacy bots also maintain in-memory caches and run blocking `gspread` calls inside async tasks (e.g., refresh loops), so migrating those flows without isolating blocking work risks double caching and stalled coroutines if both layers sleep simultaneously.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L115-L149】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L115-L213】

## 6. Live vs legacy configuration mismatches

| Concern | Live shared config | Legacy Matchmaker | Legacy WelcomeCrew |
| --- | --- | --- | --- |
| Guild scoping | `GUILD_IDS` allow-list enforced on ready/join.【F:app.py†L56-L164】 | No guild gating; bot joins any server.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L149】 | Same – no allow-list logic in legacy watcher bootstrap.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L137】 |
| Log channel | Env override with fallback to 1415330837968191629.【F:shared/config.py†L163-L206】 | Hard-coded constant `LOG_CHANNEL_ID = 1415330837968191629`.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2523】 | Optional env (`LOG_CHANNEL_ID`, default 0) controls refresh pings.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L1613】 |
| Sheet identifiers | Exposes `RECRUITMENT_SHEET_ID` / `ONBOARDING_SHEET_ID` and legacy fallbacks via `shared.sheets`.【F:shared/config.py†L168-L206】【F:shared/sheets/core.py†L84-L123】 | Uses `GOOGLE_SHEET_ID` + `WORKSHEET_NAME` and a hard-coded welcome tab reader.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L149】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】 | Depends on `GSHEET_ID`, `SHEET1_NAME`, `SHEET4_NAME`, and `CLANLIST_TAB_NAME`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L137】 |
| Watcher toggles | `WELCOME_ENABLED`, `ENABLE_WELCOME_WATCHER`, `ENABLE_PROMO_WATCHER`, `ENABLE_NOTIFY_FALLBACK` centralised.【F:shared/config.py†L191-L194】 | Per-feature flags scattered across the module (e.g., `WELCOME_ENABLED` only for the cog).【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2523】 | Rich flag surface via `env_bool` (`ENABLE_LIVE_WATCH_*`, command toggles, notify fallback).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L137】 |
| Role gating | Shared RBAC wraps admin/staff/recruiter/lead role sets from config.【F:shared/coreops_rbac.py†L15-L112】 | Role IDs defined in env but consumed ad hoc per command/cog.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L149】 | Commands largely ungated; relies on env toggles instead of role checks.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L137】 |

## 7. Key takeaways
- Live code now centralises env access and enforcement, but defaults (e.g., the fallback log channel) still match legacy values—operators should override them per deployment to avoid cross-env leakage.【F:shared/config.py†L56-L206】
- Introducing async-friendly Sheets access will require moving the blocking retry/sleep logic off the event loop and reconciling caches between `shared.sheets` and legacy modules before porting watchers wholesale.【F:shared/sheets/core.py†L52-L128】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L115-L213】
- Migrating legacy flows will demand translation layers for sheet/tab env names and feature toggles to prevent regressions when switching to the shared config schema.【F:shared/config.py†L168-L206】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2523】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L1613】
