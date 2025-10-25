# Phase 3 Discovery — Sheets Access Layer (async + cached)

## Scope & approach
- Parsed live repository modules and legacy clones under `AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM` and `AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC` to map Google Sheets usage.
- Focused on helpers that authenticate to Sheets, read/write worksheet data, and wrap retry or caching logic.
- Traced Discord command/watch flows that ultimately touch Sheets to prepare for an async + cached abstraction.

## Live repo (`.`)

### `shared/sheets/core.py`
| Function | Signature | Purpose / Notes |
| --- | --- | --- |
| `_service_account_info()` | `-> dict[str, Any]` | Loads JSON credentials from `GSPREAD_CREDENTIALS` or `GOOGLE_SERVICE_ACCOUNT_JSON`; raises if absent.【F:shared/sheets/core.py†L32-L40】 |
| `get_service_account_client()` | `-> gspread.Client` | Cached (`lru_cache`) service-account authoriser using Sheets scope. Raises if optional deps missing.【F:shared/sheets/core.py†L43-L50】 |
| `_retry_with_backoff()` | `(func, *args, attempts=None, base_delay=None, factor=None, **kwargs)` | Exponential backoff wrapper driven by env overrides `GSHEETS_RETRY_ATTEMPTS`, `GSHEETS_RETRY_BASE`, `GSHEETS_RETRY_FACTOR`; sleeps synchronously with `time.sleep`.【F:shared/sheets/core.py†L52-L81】 |
| `_resolve_sheet_id()` | `(sheet_id: str | None) -> str` | Fills `sheet_id` from `GOOGLE_SHEET_ID`/`GSHEET_ID`; strips and validates.【F:shared/sheets/core.py†L84-L90】 |
| `open_by_key()` | `(sheet_id: str | None = None)` | Workbook cache keyed by sheet id, reuses `get_service_account_client` and `_retry_with_backoff` to open the spreadsheet.【F:shared/sheets/core.py†L93-L100】 |
| `get_worksheet()` | `(sheet_id: str, name: str)` | Worksheet cache keyed by `(sheet_id, tab)` with backoff on `worksheet()` fetch.【F:shared/sheets/core.py†L103-L112】 |
| `fetch_records()` | `(sheet_id: str, worksheet: str)` | Wrapper returning `get_all_records()` with retry.【F:shared/sheets/core.py†L115-L118】 |
| `fetch_values()` | `(sheet_id: str, worksheet: str)` | Wrapper returning `get_all_values()` with retry.【F:shared/sheets/core.py†L120-L123】 |
| `call_with_backoff()` | `(func, *args, **kwargs)` | Exposes `_retry_with_backoff` for write/update helpers.【F:shared/sheets/core.py†L125-L128】 |

**Auth & env**: Service account info pulled from env, no support yet for file paths. Scope fixed to `spreadsheets`. Retry tuning uses env. Backoff uses blocking sleep (risk for async contexts).【F:shared/sheets/core.py†L27-L78】

**Caching**: Workbook + worksheet caches in module globals; `get_service_account_client` cached via `lru_cache`. No TTL invalidation.

### `sheets/onboarding.py`
- Provides Welcome Crew sheet helpers using `shared.sheets.core`. Maintains TTL caches for config and clan tags via env `SHEETS_CACHE_TTL_SEC`, `SHEETS_CONFIG_CACHE_TTL_SEC`, `CLAN_TAGS_CACHE_TTL_SEC`.【F:sheets/onboarding.py†L11-L20】
- Resolves sheet id with priority `ONBOARDING_SHEET_ID` → global IDs.【F:sheets/onboarding.py†L22-L35】
- Config tab default `Config` overridable by `ONBOARDING_CONFIG_TAB`; subsequent tab names pulled from config rows or fallback constants (`WelcomeTickets`, `PromoTickets`, `ClanList`).【F:sheets/onboarding.py†L37-L105】
- Write helpers:
  - `_ensure_headers` ensures row 1 matches expected headers using `core.call_with_backoff(ws.update, ...)` when needed.【F:sheets/onboarding.py†L130-L139】
  - `_upsert` performs sheet read + update/append with backoff wrappers; uses `_col_to_a1` to compute ranges.【F:sheets/onboarding.py†L161-L187】
  - `upsert_welcome`, `upsert_promo` specialise keys (ticket, type, created timestamp) and rely on `_upsert`.【F:sheets/onboarding.py†L189-L214】
  - `dedupe` and `_dedupe_sheet` scan cached values and delete duplicates using `delete_rows` with retries.【F:sheets/onboarding.py†L217-L267】
- `load_clan_tags` caches first-column tags for TTL, uppercases results.【F:sheets/onboarding.py†L270-L289】

**Hard-coded tabs**: Fallback names `WelcomeTickets`, `PromoTickets`, `ClanList`; config keys allow override but require sheet config row values.【F:sheets/onboarding.py†L85-L105】

**Risks**: All sheet calls still synchronous (blocking) even though module intended for async contexts; duplicates require fetching entire sheet for each upsert; caches global without invalidation hook.

### `sheets/recruitment.py`
- Mirrors onboarding patterns for recruitment workbook with TTL caches for config, clan rows, templates.【F:sheets/recruitment.py†L11-L121】
- Sheet id priority `RECRUITMENT_SHEET_ID` → global IDs.【F:sheets/recruitment.py†L24-L36】
- Config tab default `Config` via `RECRUITMENT_CONFIG_TAB`. Hard-coded fallbacks for `clans_tab` (defaults to env `WORKSHEET_NAME` or `bot_info`) and `welcome_templates_tab` (`WelcomeTemplates`).【F:sheets/recruitment.py†L39-L93】
- `fetch_clans` returns `get_all_values`, `fetch_templates` returns `get_all_records`; `fetch_clan_rows`/`fetch_welcome_templates` maintain legacy signatures.【F:sheets/recruitment.py†L95-L134】

### `recruitment/welcome.py`
- Bridges new Sheets helper into legacy recruitment cog: on setup, obtains `welcome_cog` from `ensure_loaded` shim and overrides `get_rows` to call `fetch_welcome_templates()` (cached via `sheets.recruitment`).【F:recruitment/welcome.py†L15-L24】
- Aligns allowed role ids using RBAC helper; no other Sheets I/O in live code yet.【F:recruitment/welcome.py†L25-L33】

### `shared/config.py`
- Loads env on import (`reload_config()`), capturing credential-related keys: `GSPREAD_CREDENTIALS`, `RECRUITMENT_SHEET_ID`, `ONBOARDING_SHEET_ID`, toggles for watchers, TTLs, etc.【F:shared/config.py†L200-L239】【F:shared/config.py†L345-L420】
- `get_gspread_credentials()` returns stored config string (currently just env passthrough).【F:shared/config.py†L389-L391】

### Live command/watch usage
- No live watchers yet import onboarding helpers; Welcome Crew functionality remains in legacy clone pending async rewrite.
- Recruitment welcome command uses cached template data via Sheets module but still synchronous (no background thread).【F:recruitment/welcome.py†L21-L33】

### Live risks & gaps
- Blocking retries/backoff in `shared.sheets.core` will sleep event loop if called directly from async contexts; wrappers rely on future adoption of `asyncio.to_thread` pattern seen in legacy code.
- Worksheet caches never expire; new tabs or updates require process restart.
- No centralised cache invalidation or instrumentation for dedupe/upsert operations.
- Need explicit async wrappers to avoid repeated `get_all_values()` on large sheets.

## Legacy clone — WelcomeCrew (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py`)

### Auth & env
- Direct `gspread` import; service account loaded from `GOOGLE_SERVICE_ACCOUNT_JSON`; sheet id from `GSHEET_ID`; tab names `SHEET1_NAME`/`SHEET4_NAME`; clan list tab env override; numerous toggles for watchers and commands.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L40-L88】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L124-L156】
- Maintains worksheet cache `_ws_cache` plus per-tab row indexes to avoid re-fetching entire sheet for dedupe/upsert.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L115-L156】

### Retry/backoff/caching
- `_with_backoff` retries up to six times with randomised exponential delays and throttles writes via `_sleep_ms` using `SHEETS_THROTTLE_MS` env; wraps gspread operations synchronously.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L158-L181】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L433-L468】
- `gs_client()` caches client; `get_ws()` caches worksheets, creates tabs if missing, ensures headers.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L131-L156】

### Sheet operations
- `upsert_welcome` / `upsert_promo` perform index-assisted updates, using throttled `_with_backoff` for `row_values`, `batch_update`, `append_row` calls; log diffs into state bucket.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L433-L520】
- `dedupe_sheet` scans `get_all_values()` to keep latest entries by ticket (+type/created for promo) and deletes older rows.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L523-L564】

### Watchers & commands (call graph sketches)
```
Message close event → _handle_welcome_thread(thread, ws, state)
  ↳ parse_welcome_thread_name_allow_missing
  ↳ infer_clantag_from_thread (async history scan)
  ↳ find_close_timestamp
  ↳ upsert_welcome (run via asyncio.to_thread)
        ↳ ws.row_values / ws.batch_update / ws.append_row (with backoff)
```
- `_handle_welcome_thread` invoked by `scan_welcome_channel` (manual backfill) and live thread watchers to insert/update sheet rows.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L864-L919】
- Promo flow mirrors above calling `upsert_promo`.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L920-L974】
- Commands touching Sheets:
  - `!backfill_tickets` / `scan_*` watchers run `_run_blocking` → `get_ws`/`ws_index_*` before iterating threads and calling upserts (heavy synchronous I/O offloaded via `asyncio.to_thread`).【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L861-L957】
  - `!dedupe_sheet` obtains worksheets, calls `dedupe_sheet` in thread pool, reports counts.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1216-L1233】
  - `!reload` clears caches to force next Sheets reconnect.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1234-L1241】
  - `!checksheet`, `!health` perform quick status fetches using `get_ws` and column counts.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1242-L1270】
- Live watchers include Discord event hooks and scheduled tasks; watchers rely on synchronous gspread but offload to background threads using `_run_blocking` to keep loop responsive.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1397-L1529】

### Hard-coded vs config tabs
- Defaults for `SHEET1_NAME` (`Sheet1`), `SHEET4_NAME` (`Sheet4`), clan list tab (`clanlist`), but `get_ws` auto-creates tab with headers if missing. Hard-coded header arrays for both sheets.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L40-L47】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L121-L122】

### Risks observed
- `_with_backoff` still blocking; though wrapped in `_run_blocking`, manual throttle may not prevent Discord rate-limit stalls.
- Duplicate detection does full-sheet scans; indexes may drift if concurrent edits occur outside bot.
- Mixed use of global caches and indexes can become stale if data modified externally; `ws_index_*` refresh invoked before inserts but not after updates in all paths.

## Legacy clone — Matchmaker (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py`)

### Auth & caching
- Reads `GSPREAD_CREDENTIALS`, `GOOGLE_SHEET_ID`, `WORKSHEET_NAME` on import; uses `Credentials.from_service_account_info` with read-only scope.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L103-L144】
- `get_ws(force=False)` caches worksheet handle; `get_rows(force=False)` caches `get_all_values()` for TTL from `SHEETS_CACHE_TTL_SEC`; `clear_cache()` resets state.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L120-L149】

### Sheet consumers
- Helper `read_recruiter_summary` + embed builders rely on cached rows to compose summary stats for Discord posts.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L566-L592】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L662-L697】
- `find_clan_row` and search/panel builders repeatedly call `get_rows(False)` when handling commands like `!clan`, `!clanmatch`, `!clansearch` (reads only).【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L1851-L1874】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L1709-L1848】
- Scheduled tasks:
  - `sheets_refresh_scheduler` clears cache on configured times `REFRESH_TIMES`/`TIMEZONE`, warms data, optionally logs to Discord.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L595-L658】
  - `daily_recruiters_update` builds embed via `read_recruiter_summary` and posts to `RECRUITERS_THREAD_ID` at `POST_TIME_UTC`.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L660-L723】

### Commands touching Sheets (call graph sketch)
```
!clanmatch / !clansearch → ClanMatchView actions
  ↳ user interaction triggers fetch_clans_from_rows (via cached rows)
      ↳ get_rows(False) → ws.get_all_values()

!clan <query> → find_clan_row(query) → get_rows(False)
!health → get_ws(False) + ws.row_values(1)
!reload → clear_cache()
```
- `!health` checks connectivity by calling `get_ws(False)` and retrieving first row; `!reload` clears caches for next fetch.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2054-L2091】

### Hard-coded tabs / config
- Single worksheet `WORKSHEET_NAME` default `bot_info`; summary table positions rely on fixed column indices; no config tab.

### Risks
- Cache TTL default 8h; heavy commands may read stale data unless manual reload or scheduler triggered.
- All sheet interactions synchronous; while mainly read-only, calls occur directly on event loop (no `asyncio.to_thread`), risking blocking on slow network.

## Divergences & migration notes
- Live repo centralises auth/backoff but still synchronous; legacy clones already offload blocking writes via `asyncio.to_thread`. Harmonising should expose async wrappers to avoid regressions.
- Legacy WelcomeCrew manages worksheet creation, header enforcement, diff logging — live onboarding helpers replicate logic but lack thread-safe caches or background scheduling.
- Live code introduces config-driven sheet IDs and TTL caches; legacy relies on env variables and manual reload commands. Need to reconcile config precedence and ensure watchers respect config module rather than raw env.
- Legacy matchmaker uses read-only scope; live helpers request read/write by default. Consider separate scopes per feature or maintain read-only when appropriate.
- No runtime imports from `AUDIT` remain in live repo (verified via search), so migration can focus on porting functionality rather than detangling dependencies.

## Key risks before async cached layer
1. **Blocking sleeps in retries** — `_retry_with_backoff` uses `time.sleep`, which will freeze the event loop if used without `to_thread`. Need async-aware backoff or explicit thread delegation.
2. **Cache invalidation** — Worksheet caches in live code never expire; legacy clones expose manual reload commands and scheduled refresh. Async layer must offer invalidation hooks to prevent stale data.
3. **Duplicate full-sheet fetches** — Helpers like `_upsert` call `ws.get_all_values()` on every operation; large sheets will dominate runtime. Introduce range-based lookups or maintain incremental indexes.
4. **Error handling gaps** — Live helpers swallow write exceptions via bare `except` in some dedupe operations (legacy too). Async layer should propagate or log structured failures for monitoring.
5. **Configuration drift** — Hard-coded tab names differ (`Sheet1`/`Sheet4` vs `WelcomeTickets`/`PromoTickets`). Harmonise config keys so async layer resolves consistently across environments.

## Next steps for async + cached layer
- Wrap `shared.sheets.core` with `asyncio.to_thread` utilities or refactor to use an async Sheets client (if available) to avoid blocking.
- Provide TTL-aware caches with explicit invalidation (e.g., context-managed caching service) and integrate scheduled refresh similar to legacy bots.
- Consolidate config access via `shared.config` so watchers do not read raw env variables directly.
- Document a unified schema for onboarding/promotions tabs to prevent header drift and ease dedupe/upsert logic migration.

Doc last updated: 2025-10-15 (v0.9.5)
