# Phase 3 Discovery — Sheets Access Layer (async + cached)

## Scope & sources
- Live repository (`.`)
- Legacy Matchmaker clone (`AUDIT/20251010_src/MM`)
- Legacy WelcomeCrew clone (`AUDIT/20251010_src/WC`)

Unless noted, modules rely on synchronous `gspread` calls. All paths use service-account JSON loaded from environment variables.

## Live repository snapshot

### Shared Sheets core (`shared/sheets/core.py`)
- **Authentication**: `_service_account_info()` deserialises `GSPREAD_CREDENTIALS` (preferred) or `GOOGLE_SERVICE_ACCOUNT_JSON`; scopes fixed to `https://www.googleapis.com/auth/spreadsheets` via `Credentials.from_service_account_info`. `get_service_account_client()` is memoised with `functools.lru_cache` to avoid redundant auth handshakes.【F:shared/sheets/core.py†L11-L49】
- **Workbook/worksheet caching**: `_WorkbookCache` and `_WorksheetCache` store handles keyed by sheet ID and tab name. `open_by_key()` and `get_worksheet()` populate caches after a retry-wrapped fetch.【F:shared/sheets/core.py†L23-L113】
- **Retry/backoff**: `_retry_with_backoff()` applies exponential backoff with defaults drawn from `GSHEETS_RETRY_ATTEMPTS`, `GSHEETS_RETRY_BASE`, and `GSHEETS_RETRY_FACTOR`, sleeping synchronously between attempts. Exposed helpers `fetch_records`, `fetch_values`, and `call_with_backoff` wrap worksheet operations with the same strategy.【F:shared/sheets/core.py†L27-L125】
- **Sheet resolution**: `_resolve_sheet_id()` falls back to `GOOGLE_SHEET_ID` or `GSHEET_ID`. Missing configuration raises immediately.【F:shared/sheets/core.py†L84-L113】

### Recruitment accessors (`sheets/recruitment.py`)
- **Config & caching**: `_load_config()` caches a lowercased key/value map from a configurable tab (`RECRUITMENT_CONFIG_TAB`, default `Config`) for `SHEETS_CONFIG_CACHE_TTL_SEC`. Clan rows (`fetch_clans`) and template rows (`fetch_templates`) cache Sheets responses for `SHEETS_CACHE_TTL_SEC`.【F:sheets/recruitment.py†L11-L119】
- **Hard-coded defaults**: Without config rows, tabs default to `bot_info` for clans (with legacy override `WORKSHEET_NAME`) and `WelcomeTemplates` for templates. Sheet ID resolution prefers `RECRUITMENT_SHEET_ID` then the shared fallbacks.【F:sheets/recruitment.py†L24-L105】
- **Backward compatibility shims**: `fetch_clan_rows()` and `fetch_welcome_templates()` expose legacy signatures (the latter allows overriding the tab name, bypassing cached config).【F:sheets/recruitment.py†L123-L134】
- **Risk**: All fetches call synchronous `gspread` helpers; caches are module-level globals without eviction except TTL.【F:shared/sheets/core.py†L52-L81】

### Onboarding accessors (`sheets/onboarding.py`)
- **Config mirror**: Matches recruitment helpers but tuned for WelcomeCrew tabs (`WelcomeTickets`, `PromoTickets`, `ClanList`). Sheet ID resolves from `ONBOARDING_SHEET_ID`. Caches exist for config, clan tags, and dedupe TTLs (env overrides `SHEETS_CACHE_TTL_SEC`, `SHEETS_CONFIG_CACHE_TTL_SEC`, `CLAN_TAGS_CACHE_TTL_SEC`).【F:sheets/onboarding.py†L11-L105】
- **Write helpers**: `_ensure_headers()`, `_upsert()`, `upsert_welcome()`, `upsert_promo()`, and `dedupe()` wrap worksheet writes with `core.call_with_backoff`. Deduplication scans the full sheet, keeps the newest duplicate, and deletes others individually. All work happens synchronously, so callers must offload to threads for async safety.【F:sheets/onboarding.py†L84-L244】
- **Clan tag cache**: `load_clan_tags()` reuses cached `fetch_values` results to build an uppercased tag list for tag inference.【F:sheets/onboarding.py†L256-L289】

### Consumers & integration points
- `recruitment/welcome.py` wires legacy `Welcome` cog instances to `sheets.recruitment.fetch_welcome_templates()` for template data, also tightening allowed-role configuration. The loader (`recruitment.ensure_loaded`) is currently a stub, so no runtime sheet calls happen yet in the live bot.【F:recruitment/welcome.py†L1-L34】【F:recruitment/__init__.py†L1-L10】
- No live module imports `sheets/onboarding` yet; future WelcomeCrew adapters must offload its synchronous helpers to background threads for async hygiene.【F:sheets/onboarding.py†L84-L244】

### Environment surfaces
- Secrets & auth: `GSPREAD_CREDENTIALS`, `GOOGLE_SERVICE_ACCOUNT_JSON` (service account payloads).【F:shared/sheets/core.py†L32-L49】
- Sheet identifiers: `RECRUITMENT_SHEET_ID`, `ONBOARDING_SHEET_ID`, `GOOGLE_SHEET_ID`, `GSHEET_ID`.【F:sheets/recruitment.py†L24-L36】【F:sheets/onboarding.py†L22-L34】
- Retry tuning: `GSHEETS_RETRY_ATTEMPTS`, `GSHEETS_RETRY_BASE`, `GSHEETS_RETRY_FACTOR`.【F:shared/sheets/core.py†L27-L29】
- Cache tuning: `SHEETS_CACHE_TTL_SEC`, `SHEETS_CONFIG_CACHE_TTL_SEC`, `CLAN_TAGS_CACHE_TTL_SEC`.【F:sheets/recruitment.py†L11-L18】【F:sheets/onboarding.py†L11-L18】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L117-L233】
- Tab overrides: `RECRUITMENT_CONFIG_TAB`, `ONBOARDING_CONFIG_TAB`, and the legacy fallback `WORKSHEET_NAME` (used when config rows omit the clan tab).【F:shared/sheets/core.py†L27-L90】【F:sheets/recruitment.py†L24-L105】【F:sheets/onboarding.py†L22-L104】

## Legacy Matchmaker (AUDIT/20251010_src/MM/bot_clanmatch_prefix.py)

### Auth & setup
- **Environment**: `GSPREAD_CREDENTIALS`, `GOOGLE_SHEET_ID`, `WORKSHEET_NAME` select the recruitment worksheet. Scope limited to `spreadsheets.readonly`.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L141】
- **Client lifecycle**: `get_ws()` instantiates a fresh `gspread` client on every reconnect and caches the worksheet handle globally; `get_rows()` caches `worksheet.get_all_values()` for `CACHE_TTL` (default 8h).【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L123-L144】
- **Cache refresh**: `clear_cache()` resets worksheet/row caches.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L145-L166】 `sheets_refresh_scheduler()` runs thrice daily (`REFRESH_TIMES`, default `02:00,10:00,18:00`) to clear caches, immediately re-fetch rows, and optionally log to `LOG_CHANNEL_ID`.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L145-L166】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L596-L666】

### Read paths & consumers
- `get_rows(force=False)` is the single source for the clan matrix. Major callers:
  - **`ClanMatchView.search`** (`!clanmatch` recruiter flow) → `get_rows()` → `worksheet.get_all_values()`; filters results in-place before building embeds. Blocking call triggered directly inside interaction handler.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1415-L1510】
  - **`ClanMatchView._maybe_refresh`** (auto-refresh recruiter panel after filter tweaks) reuses `get_rows()` while processing UI interactions.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1228-L1300】
  - **`find_clan_row`** (used by `!clan <tag>` profile command and reaction flips) pulls from cached rows for targeted lookups.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1851-L1868】
  - **`read_recruiter_summary`** (drives `daily_recruiters_update` task and `build_recruiters_summary_embed`) parses summary blocks from `get_rows()` output.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L566-L591】
  - **Welcome templates**: `get_welcome_rows()` (bottom of file) opens the workbook anew, reads `WELCOME_SHEET_TAB`, and feeds templates into the legacy `Welcome` cog without caching.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- Call graph sketch:
  - `!clanmatch`/`!clansearch` commands → `ClanMatchView.search` → `get_rows()` → Sheets
  - `!clan <tag>` → `find_clan_row` → `get_rows()` → Sheets【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1851-L1868】
  - `daily_recruiters_update` task → `build_recruiters_summary_embed` → `read_recruiter_summary` → `get_rows()` → Sheets
  - `!welcome-refresh` (via welcome cog) → `get_welcome_rows()` → Sheets

### Risks & gaps
- All Sheets calls run on the main asyncio event loop; `get_rows()` and `get_welcome_rows()` invoke blocking `gspread` network IO and parsing.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L136-L151】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- Backoff is absent around `worksheet.get_all_values()`/`get_all_records()` beyond the scheduler retries. Transient 429/timeout errors bubble straight into UI flows.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L136-L151】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1415-L1510】
- Hard-coded tab defaults: `WORKSHEET_NAME` (default `bot_info`) and `WELCOME_SHEET_TAB` (`WelcomeTemplates`).【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L104】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- Duplicate fetches: welcome templates re-auth each call instead of reusing the cached client.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】

## Legacy WelcomeCrew (AUDIT/20251010_src/WC/bot_welcomecrew.py)

### Auth & caching
- **Environment**: `GOOGLE_SERVICE_ACCOUNT_JSON` and `GSHEET_ID` identify the workbook; tab names driven by `SHEET1_NAME` (welcome), `SHEET4_NAME` (promo), and `CLANLIST_TAB_NAME`. Feature flags toggle watchers/commands.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L156】
- **Client cache**: `gs_client()` memoises the `gspread` client; `_ws_cache` stores worksheet handles per tab after ensuring headers.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L131-L156】
- **Index caches**: `_index_simple` (ticket → row) and `_index_promo` (ticket/type/created → row) memoise row positions for upserts. `_clan_tags_cache` stores tag lists for `CLAN_TAGS_CACHE_TTL_SEC`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L117-L371】

### Retry/backoff
- `_with_backoff()` wraps writes with exponential backoff (`delay` doubles up to 8s) and jitter, classifying transient errors by keyword. `_run_blocking()` offloads blocking calls via `asyncio.to_thread`; adoption is partial.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L158-L181】
- `_sleep_ms(SHEETS_THROTTLE_MS)` enforces per-call throttling (default 200 ms) before writes.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L158-L181】

### Read/write modules
- `get_ws(name, headers)` ensures worksheet existence, adds missing tabs, and normalises headers.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L139-L156】
- `ws_index_welcome` / `ws_index_promo` build indexes via full-sheet scans; upserts consult caches first, then re-scan before inserts.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L373-L433】
- `upsert_welcome` / `upsert_promo` perform read-modify-write cycles with diff logging and throttled `batch_update` or `append_row` calls. Promo writes detect duplicates via `_find_promo_row_pair` fallback.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L420-L520】
- `dedupe_sheet` (via `dedupe()` command) removes duplicates by recomputing indexes and deleting extra rows.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L217-L267】
- `_load_clan_tags()` reads the clanlist tab, builds regex caches for tag inference, and is invoked synchronously from message parsing helpers (`_match_tag_in_text`, `_pick_tag_by_suffix`).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L293-L371】

### Watchers & commands relying on Sheets
- **Startup**: `setup_hook` runs `_run_blocking(_load_clan_tags, True)` to warm caches.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L281-L291】
- **Live watchers**:
  - `on_thread_create` / `on_ready` / watcher flows call `_load_clan_tags()` and upsert helpers while reacting to thread events.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1540-L1629】
  - `on_message` pipelines infer tags (`_load_clan_tags`) and schedule `_finalize_welcome`/`_finalize_promo`, which call `get_ws` and `upsert_*` via `_run_blocking`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L857】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L894-L967】
  - Watchdog/task loops (`scheduled_refresh_loop`) refresh clan tags thrice daily and prewarm worksheets.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1540-L1615】
- **Commands**:
  - `!sheetstatus`/`!health` (when enabled) ping `get_ws`/`ws.row_values` for status.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1252】
  - `!backfill` / `!promo-backfill` spawn scans that iterate threads and call `_handle_*` helpers; each helper fetches/upserts rows with `_run_blocking`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L857】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L894-L967】
  - `!dedupe` triggers `dedupe_sheet` for both tabs.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1216-L1232】
  - `!reload` refreshes `_load_clan_tags` and worksheet caches.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1234-L1240】
- Call graph sketch highlights (Sheets touchpoints):
  - Thread events → `_finalize_welcome` / `_finalize_promo` → `_run_blocking(get_ws)` → `_run_blocking(upsert_*)` → Sheets
  - `!backfill` → `_handle_welcome_thread` / `_handle_promo_thread` → `_run_blocking(upsert_*)` → Sheets
  - Message parsing → `_match_tag_in_text` → `_load_clan_tags` → Sheets (blocking on cache miss)
  - Scheduled refresh → `_run_blocking(_load_clan_tags)` + `_run_blocking(get_ws, ...)` → Sheets

### Risks & gaps
- Despite `_run_blocking`, several hot paths still call `_load_clan_tags()` synchronously (e.g., `_match_tag_in_text`, `_pick_tag_by_suffix`), blocking the gateway during cache misses or refreshes.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L293-L371】
- Index rebuilds call `ws.get_all_values()` on the event loop when `_run_blocking` is omitted.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L373-L433】
- Backfill operations rely on repeated full-sheet scans (`get_all_values`, `col_values`), which can exceed rate limits without stronger batching or caching.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L864-L967】
- Hard-coded defaults: `SHEET1_NAME`, `SHEET4_NAME`, `CLANLIST_TAB_NAME`, and column heuristics (fallback to column B) baked into the loaders.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L347】

## Divergences & migration notes
- Live repository centralises auth/backoff and introduces TTL caches but still exposes synchronous APIs. Legacy bots reimplement similar patterns locally with inconsistent retries and manual throttling.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L136-L151】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L158-L181】
- Legacy Matchmaker hard-codes read-only scope and lacks write support; WelcomeCrew performs writes with bespoke throttling/backoff. Live adapters must support both read and write scenarios.
- Clan tag caching diverges: live `sheets/onboarding.load_clan_tags()` uses cached `fetch_values`, whereas legacy `_load_clan_tags()` rebuilds regex caches synchronously and stores normalised tags. Unifying behaviour requires async-safe caching and regex reuse.【F:sheets/onboarding.py†L256-L289】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L293-L347】
- No runtime imports in live code reference the `AUDIT` tree; migration will need explicit bridging modules to replace legacy commands before those clones can be retired.【F:recruitment/__init__.py†L1-L10】

## Identified risks for async + cache layer
1. **Blocking IO in async contexts**: Current helpers (`shared.sheets.core` and legacy modules) use synchronous `time.sleep` and `gspread` calls, which must move to worker threads (or async client) to avoid event-loop stalls.【F:shared/sheets/core.py†L52-L81】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L136-L151】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L293-L347】
2. **Duplicate fetches & cache invalidation**: Multiple layers of caching (worksheet, records, templates) lack coordinated invalidation; forcing refreshes currently requires manual `force=True` flags or cache-clearing commands.【F:sheets/recruitment.py†L95-L140】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L145-L166】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1270】
3. **Error handling gaps**: Legacy reads lack retries; writes rely on keyword detection for transient errors. Centralising retry/backoff with structured exception inspection will reduce silent skips.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L158-L181】
4. **Configuration drift**: Tab names and sheet IDs rely on overlapping env vars (`RECRUITMENT_SHEET_ID`, `GOOGLE_SHEET_ID`, etc.). A shared config contract is needed to avoid mismatched sources across bots.【F:sheets/recruitment.py†L24-L104】【F:sheets/onboarding.py†L22-L104】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L104】
5. **Watcher coupling**: WelcomeCrew watchers trigger Sheets operations in message handlers and thread events; migrating to an async access layer must ensure caching (especially clan tags) is pre-warmed or served from in-memory structures to keep latency low.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L293-L347】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1540-L1615】

## Next steps toward the async cached layer
- Design a shared async wrapper (likely `asyncio.to_thread` backed) that reuses the `shared.sheets.core` caching logic but exposes awaitable APIs and centralised retries/backoff.【F:shared/sheets/core.py†L52-L125】
- Extract clan-tag and template fetch logic into typed services, allowing both Matchmaker and WelcomeCrew to share caches.【F:sheets/recruitment.py†L95-L140】【F:sheets/onboarding.py†L256-L289】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1270】
- Gradually replace legacy direct `gspread` calls with the new adapter, starting with read-heavy paths (`get_rows`, `_load_clan_tags`) before tackling write flows (`upsert_*`).【F:sheets/onboarding.py†L189-L267】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L857】

Relates to #20, #12, #13, #6.
