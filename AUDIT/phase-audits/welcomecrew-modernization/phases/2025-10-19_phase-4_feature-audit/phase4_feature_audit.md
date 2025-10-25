# Phase 4 Recruitment Feature Audit (2025-10-19)

## A. Evidence Map

### 1. Member Panel (`!clansearch`)
- **Unified**: Loader stub only in `recruitment.search`; `ensure_loaded` is a no-op, so no commands/listeners/schedulers register yet.
- **Legacy Matchmaker (MM)**: Prefix command `!clansearch` launches `ClanMatchView` in search mode with owner-locked interactions. `MemberSearchPagedView` and `SearchResultFlipView` handle pagination and lite/entry/profile toggles, embedding crest thumbnails via attachments. Replies stay in the invoking channel; repeated summons edit the original panel. RBAC allows any member, enforced by interaction checks that redirect non-owners to summon their own panel.
- **Legacy WelcomeCrew (WC)**: No member browsing feature.
- **Data & caching**: Reads `bot_info` tab (columns A–AF) through `get_rows`. Columns cover rank, clan name/tag, level, spots, leadership, filters (P–U), entry criteria (V–AB), and reserved/comment/additional requirement fields (AC–AE) plus inactives (AF). Code merges display strings (`build_entry_criteria_classic`, `make_embed_for_row_lite`). Cached in-process; no sheet writes.
- **Logging / env**: Uses synchronous `get_rows`; basic prints only. `SEARCH_RESULTS_SOFT_CAP` env var caps results.

### 2. Recruiter Panel (`!clanmatch`)
- **Unified**: Not implemented; loader stub only.
- **Legacy MM**: Prefix command `!clanmatch` gated to recruiter/admin roles (`_allowed_recruiter`). Builds `ClanMatchView` with dropdowns (CB/Hydra/Chimera/Playstyle) and toggle buttons (CvC, Siege, roster mode, reset, search). Search reuses sheet reads; recruiter embeds use "classic" layout and auto-refresh result messages on filter change. Supports thread redirection via `PANEL_THREAD_MODE`/`PANEL_FIXED_THREAD_ID`. Owner-locked; cooldown 1 use per 2 seconds.
- **Legacy WC**: No recruiter panel logic.
- **Data & caching**: Same `bot_info` columns; recruiter embeds append reserved spots and comments. Reads manual "open spots" counts and "reserved" notes verbatim. No sheet writes.
- **Channels / logging / env**: Optional fixed-thread routing, stdout logging, env IDs for recruiter roles and threads.

### 3. Recruitment Welcome (`!welcome`)
- **Unified**: `recruitment.welcome.WelcomeBridge` cog registers `!welcome`, using cached templates (`templates` bucket) and CoreOps RBAC helpers. Logs via `runtime.send_log_message`. Requires WelcomeTemplates sheet tab.
- **Legacy MM**: `welcome.py` cog with same command, richer template expansion (placeholders, emoji tokens, general notice, logging). Uses manual cache reload, env-driven role allow list. No sheet writes; does not touch `bot_info`.
- **Legacy WC**: Not applicable (WelcomeCrew handles thread watchers only).
- **Data & caching**: Unified `sheets/recruitment` registers async cache buckets `clans` (bot_info) and `templates` (WelcomeTemplates) with TTL 3h/7d. Legacy MM uses synchronous `get_welcome_rows` with `WELCOME_SHEET_TAB`. No sheet writes in either implementation.
- **Logging / env**: Unified logs via runtime; legacy logs to configured channel. Unified RBAC leans on CoreOps roles; legacy uses `WELCOME_ALLOWED_ROLES` env var.

### 4. Daily Recruiter Report (digest)
- **Unified**: Not ported; runtime only schedules Phase-3 caches (`clans`, `templates`, `clan_tags`). No recruiter digest job.
- **Legacy MM**: `_locate_summary_headers` and `read_recruiter_summary` parse summary table at top of `bot_info` sheet (requires headers "open spots", "inactives", "reserved spots"). `daily_recruiters_update` (`tasks.loop`) posts daily to configured thread and mentions optional roles. Started in `on_ready`. Logging via stdout; lacks retries.
- **Legacy WC**: No recruiter digest.
- **Data & caching**: Reads `bot_info` summary rows only; no writes. Needs `RECRUITERS_THREAD_ID`, `ROLE_ID_RECRUITMENT_COORDINATOR`, `ROLE_ID_RECRUITMENT_SCOUT` env vars.
- **Channels / scheduling**: Posts to text channel/thread; scheduler tied to `tasks.loop` at 17:30 UTC with auto-start in `on_ready`.

### 5. Target Clan Select (recruiter-only picker)
- **Unified**: No implementation.
- **Legacy MM**: Panels surface candidate clans but do not persist a recruiter selection. Closest elements are search results plus `find_clan_row`/`!clan` command.
- **Legacy WC**: `TagPickerView` provides dropdown picker in threads with paging and fallback text—potential scaffolding for future clan-select UI (already recruiter-targeted in watcher context).
- **Data & caching**: Would rely on `clan_tags` Phase-3 cache for dropdown choices and `clans` cache for context.
- **RBAC / channels**: Future implementation must use recruiter RBAC helpers (`is_recruiter`) and existing panel thread routing envs.

### 6. Reserve Spot in Target Clan
- **Unified**: No reservation workflow.
- **Legacy MM**: Displays `Reserved` column (AC) as plain text in recruiter embeds and daily summary; never edits it. Assumes manual maintenance of reservation name/counts in `bot_info`. No expiry handling.
- **Legacy WC**: No reservation logic.
- **Data & caching**: Reads `Reserved` (AC) and `Spots` (E) columns; read-only. No schema for duration/status, so explicit expiry requires new sheet columns before automation.

### Sheets Model Reality & Phase-3 Cache Surface
- `bot_info` expectations: columns A–AF holding manual spots/inactives/reserved entries and entry criteria fragments; merged display strings built in Python (`build_entry_criteria_classic`, `make_embed_for_row_*`).
- Legacy daily summary scans for header row containing "open spots", "inactives", "reserved spots" and parses integers.
- Unified cache layer registers `clans`, `templates`, and `clan_tags` buckets with refresh jobs on startup.

## B. Presence Matrix (feature readiness)

| Feature | Unified | Legacy MM | Legacy WC |
| --- | --- | --- | --- |
| Member Panel | **Absent** – loader stub only; no commands registered. | **Present** – `!clansearch`, panel views, embeds, owner-locking. | **Absent** – watcher bot only. |
| Recruiter Panel | **Absent** – no commands registered yet. | **Present** – `!clanmatch` workflow, recruiter RBAC, thread routing. | **Absent** – no recruiter tooling. |
| Recruitment Welcome | **Present (partial parity)** – `WelcomeBridge` with cached templates/logging. | **Present (richer)** – legacy cog with placeholder expansion, notices, toggles. | **Absent** – not part of WelcomeCrew. |
| Daily Recruiter Report | **Absent** – runtime lacks digest scheduler. | **Present** – summary parser + scheduled post loop. | **Absent** – watchers only. |
| Target Clan Select | **Absent** – no selection UI yet. | **Partial (display only)** – panels surface candidates without persistence. | **Partial (picker infra)** – thread tag picker scaffolding. |
| Reserve Spot in Target Clan | **Absent** – no reservation flow. | **Partial (read-only)** – displays reserved counts without writes/expiry. | **Absent** – no reservation tooling. |

## C. Proposed Unified Module Keys (toggleable)

- **`member_panel`**
  - Files: `recruitment/search.py` plus future panel port under `recruitment/`.
  - Commands/events: `!clansearch`, member interaction views (`MemberSearchPagedView`, `SearchResultFlipView`).
  - Data deps: `sheets.recruitment.fetch_clans` (`clans` cache) covering `bot_info` columns A–AF, including manual "Spots" (E), entry criteria (V–AB), `Reserved` (AC).
  - Platform services: CoreOps RBAC helpers (owner lock only), Discord attachments for crests, Sheets cache service.
- **`recruiter_panel`**
  - Files: `recruitment/search.py`, new recruiter panel implementation.
  - Commands/events: `!clanmatch`, recruiter-only view with search/reset buttons, reuse `find_clan_row`.
  - Data deps: `bot_info` columns including `Reserved` (AC) and `Inactives` (AF); requires `clans` cache and panel thread env config (`shared.config.get_panel_thread_mode`).
  - Platform services: CoreOps RBAC (`is_recruiter`), Discord thread handling, Sheets cache (`clans`).
- **`recruitment_welcome`**
  - Files: `recruitment/welcome.py`.
  - Commands/events: `!welcome` plus future refresh/status hooks.
  - Data deps: `sheets.recruitment.get_cached_welcome_templates` (`templates` bucket) from WelcomeTemplates tab.
  - Platform services: CoreOps tiers/logging, Sheets cache.
- **`recruitment_reports`**
  - Files: new scheduler module (e.g., `recruitment/reports.py` or `modules/recruitment_reports`).
  - Commands/events: daily loop, optional manual trigger.
  - Data deps: `bot_info` summary table (manual "open/reserved/inactives"), `clans` cache; env vars `RECRUITERS_THREAD_ID`, coordinator/scout roles.
  - Platform services: Runtime scheduler/log channel, Discord thread posting.
- **`placement_target_select`**
  - Files: new module under `recruitment/` leveraging shared UI components (reuse `TagPickerView`).
  - Commands/events: recruiter-only dropdown/modal to pick target clan from `clan_tags` cache; integrate with panels or dedicated command.
  - Data deps: `clan_tags` cache (Sheets `clanlist`) plus `clans` cache for context.
  - Platform services: CoreOps RBAC, Discord UI components, Sheets cache.
- **`placement_reservations`**
  - Files: new module for reserve actions.
  - Commands/events: recruiter action/button/modal to reserve spots with explicit duration input; scheduler for expiry notifications once sheet schema supports it.
  - Data deps: currently only `Reserved` (AC) string; lacks structured fields for duration/status. Future automation needs new sheet columns (e.g., `reserved_until`, `reserved_by`). Reads/writes would target `bot_info`.
  - Platform services: Sheets write access, Discord interactions, CoreOps RBAC, runtime scheduler for expiries.

## D. Minimal Hook Points (Unified)

- **Startup gating**: Wrap recruitment module loads inside `Runtime.load_extensions` (`shared/runtime.py`, lines 574–579) with `is_enabled('member_panel')`, `is_enabled('recruiter_panel')`, `is_enabled('recruitment_welcome')`, etc., to block registration when toggled off.
- **Module-level gating**: Within `recruitment.search.setup`, guard future panel registration before invoking legacy port logic using the same `is_enabled` checks. Current stub only calls `ensure_loaded`.
- **Welcome cog**: Apply `is_enabled('recruitment_welcome')` in `recruitment/welcome.setup` before `bot.add_cog`, while keeping cache registration available regardless of toggle state.
- **Future schedulers**: When porting the daily digest, gate scheduler initialization either within runtime post-cache registration or inside the module so disabled toggles prevent loop registration.

## E. Risks & Unknowns

- **Hard-coded IDs & env sprawl**: Legacy panels depend on `PANEL_THREAD_MODE`, `PANEL_FIXED_THREAD_ID`, and recruiter role env lists parsed at import time; misconfigurations silently break flows. Unified `shared.config` still expects valid IDs.
- **Synchronous Sheets I/O**: Legacy `get_rows` and summary parsing use blocking gspread calls; ports must rely on async cache layer to avoid gateway stalls.
- **Import-time state**: Globals such as `ACTIVE_PANELS`, `REACT_INDEX`, and env parsing run at import; toggling modules off/on without reinitialization risks stale message IDs/role caches.
- **Logging gaps**: Legacy recruiter flows log via stdout; unified modules should use structured runtime logging for observability when toggled.
- **Reservations data gap**: `bot_info` only offers free-form `Reserved` string (AC) and numeric `Spots`/`Inactives`; automation for explicit expiry demands new sheet columns before storing metadata.
- **Scheduler fragility**: Daily digest loop posts synchronously without retries, assuming channel fetch succeeds; porting must handle missing thread IDs and Discord HTTP errors gracefully.
- **UI reuse uncertainty**: Target clan picker likely needs WelcomeCrew's `TagPickerView`; adapting thread-based UI to recruiter context requires permission review and RBAC hardening.

Doc last updated: 2025-10-19 (v0.9.5)
