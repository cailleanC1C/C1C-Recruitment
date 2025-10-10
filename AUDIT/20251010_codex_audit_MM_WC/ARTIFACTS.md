# Artifacts — Matchmaker & WelcomeCrew (2025-10-10)

## File tree & one-line purposes

### Matchmaker (Achievements)
- `AUDIT/20251010_src/MM/c1c_claims_appreciation.py` — Monolithic entrypoint wiring keep-alive HTTP, config loading, Discord bot setup, claim listeners, and admin commands.【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L19-L166】【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L1431-L1661】
- `AUDIT/20251010_src/MM/cogs/ops.py` — CoreOps cog that exposes health/digest/reload/checksheet/env/reboot prefix commands backed by shared embed builders.【F:AUDIT/20251010_src/MM/cogs/ops.py†L1-L305】
- `AUDIT/20251010_src/MM/cogs/shards/cog.py` — Shards & Mercy cog handling OCR prompts, shard thread listeners, and `!ocr`/`!shards`/`!mercy` commands.【F:AUDIT/20251010_src/MM/cogs/shards/cog.py†L41-L418】
- `AUDIT/20251010_src/MM/cogs/shards/views.py` — Discord UI modals and views for shard count entry, pull tracking, and tag pickers used by the shards cog.【F:AUDIT/20251010_src/MM/cogs/shards/views.py†L1-L40】
- `AUDIT/20251010_src/MM/cogs/shards/renderer.py` — Embed builders for shard summaries, pity lines, and roster pagination.【F:AUDIT/20251010_src/MM/cogs/shards/renderer.py†L1-L36】
- `AUDIT/20251010_src/MM/cogs/shards/sheets_adapter.py` — gspread helpers that read/write shard summary, snapshot, and event worksheets.【F:AUDIT/20251010_src/MM/cogs/shards/sheets_adapter.py†L120-L200】
- `AUDIT/20251010_src/MM/cogs/shards/ocr.py` — OCR utilities (pytesseract glue, parsing helpers) feeding shard automation.【F:AUDIT/20251010_src/MM/cogs/shards/ocr.py†L1-L34】
- `AUDIT/20251010_src/MM/cogs/shards/constants.py` — Enumerations and display order constants for shard types and pity labels.【F:AUDIT/20251010_src/MM/cogs/shards/constants.py†L1-L32】
- `AUDIT/20251010_src/MM/claims/ops.py` — CoreOps embed builders for health, digest, config, env, and checksheet responses.【F:AUDIT/20251010_src/MM/claims/ops.py†L1-L37】
- `AUDIT/20251010_src/MM/claims/help.py` — Help embed/command implementation for CoreOps topics and staff guidance.【F:AUDIT/20251010_src/MM/claims/help.py†L33-L143】
- `AUDIT/20251010_src/MM/core/prefix.py` — Shared prefix helper that prioritises scoped prefixes (`!sc`, `!rem`, `!wc`, `!mm`).【F:AUDIT/20251010_src/MM/core/prefix.py†L6-L27】

### WelcomeCrew
- `AUDIT/20251010_src/WC/bot_welcomecrew.py` — Entrypoint encapsulating env configuration, Sheets helpers, Discord commands, thread watchers, watchdog loop, and aiohttp keep-alive server.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L32-L1813】
- `AUDIT/20251010_src/WC/docs/` — Supplemental markdown (not executed) retained from prior review; no runtime code (not cited for execution).

## API surface inventory

### Discord commands & listeners
- **Matchmaker commands:**
  - Staff config & testing commands (`!testconfig`, `!configstatus`, `!reloadconfig`, `!listach`, `!findach`, `!testach`, `!testlevel`, `!flushpraise`, `!ping`) defined in the monolith with `_is_staff` checks.【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L1215-L1378】
  - CoreOps administrative commands (`!health`, `!digest`, `!reload`, `!checksheet`, `!env`, `!reboot`/`restart`/`rb`) served by `cogs/ops.py`.【F:AUDIT/20251010_src/MM/cogs/ops.py†L59-L305】
  - Shards automation commands (`!ocr`, `!shards`, `!mercy`) scoped to shard threads with staff overrides.【F:AUDIT/20251010_src/MM/cogs/shards/cog.py†L346-L453】
- **Matchmaker listeners:** Member update and message handlers trigger level embeds, claim workflows, and audit logging; gateway hooks update watchdog telemetry.【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L1431-L1587】
- **WelcomeCrew commands:** Prefix commands for environment checks, ping, sheet status, backfill orchestration, clan tag debug, dedupe, cache reload, health, checksheet, reboot, and watch status, plus slash `/help`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L237-L279】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1007-L1280】
- **WelcomeCrew listeners & tasks:** Thread message/update handlers manage welcome/promo ticket logging, watchers auto-join threads, watchdog loop enforces reconnects, and gateway hooks update last-event telemetry.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1398-L1803】

### Google Sheets & HTTP integrations
- **Matchmaker Sheets access:** `load_config` uses a service-account to read `General`, `Categories`, `Achievements`, `Levels`, and `Reasons`; shards adapter writes to `SUMMARY_MSGS`, `SHARD_SNAPSHOTS`, and `SHARD_EVENTS` via `append_row`/`update`.【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L145-L279】【F:AUDIT/20251010_src/MM/cogs/shards/sheets_adapter.py†L139-L200】
- **Matchmaker HTTP endpoints:** Flask keep-alive exposes `GET /` returning `ok` for platform probes.【F:AUDIT/20251010_src/MM/c1c_claims_appreciation.py†L19-L29】
- **WelcomeCrew Sheets access:** Cached `gs_client` opens the configured spreadsheet, ensures headers, indexes Sheet1/Sheet4, performs dedupe, and powers backfill/dedupe commands; `_load_clan_tags` fetches the clanlist tab via `get_all_values`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L115-L405】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1216-L1269】
- **WelcomeCrew HTTP endpoints:** aiohttp server registers `/`, `/ready`, `/health`, and `/healthz` JSON routes that reflect gateway status, latency, and `STRICT_PROBE` mode, closing the shared `ClientSession` on cleanup.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1482-L1538】
