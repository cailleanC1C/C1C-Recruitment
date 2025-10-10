# Artifacts Inventory

## File Tree & Purposes
- `AUDIT/20251010_src/MM/README.md` — Product overview, feature list, and sheet schema for Matchmaker (panels, welcomes, daily summary, health endpoints).【F:AUDIT/20251010_src/MM/README.md†L1-L80】
- `AUDIT/20251010_src/MM/bot_clanmatch_prefix.py` — Main Matchmaker bot: prefix commands, panels, sheet cache, daily summary, cleanup, watchdog, and aiohttp server integration.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L98-L2544】
- `AUDIT/20251010_src/MM/welcome.py` — Welcome Cog handling templated embeds, permissions, and sheet-driven placeholders.【F:AUDIT/20251010_src/MM/welcome.py†L303-L443】
- `AUDIT/20251010_src/WC/README.md` — WelcomeCrew product notes covering watchers, backfill, sheet tabs, and command catalog.【F:AUDIT/20251010_src/WC/README.md†L1-L80】
- `AUDIT/20251010_src/WC/bot_welcomecrew.py` — WelcomeCrew bot core: env toggles, commands, watchers, sheet writes, watchdog, health server, and startup routine.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L40-L1767】

## Discord API Surface
- **Matchmaker prefix commands**: `!clanmatch`, `!clansearch`, `!clan <tag>`, `!welcome*`, `!reload`, `!health`, `!ping`, `!mmhealth`; welcome Cog enforces role checks before posting embeds.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1566-L1808】【F:AUDIT/20251010_src/MM/welcome.py†L303-L443】
- **Matchmaker listeners & tasks**: reaction toggle for 💡 embeds, daily recruiter summary loop, cleanup loop, socket heartbeat events, watchdog loop.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L2297】
- **WelcomeCrew prefix commands**: `!env_check`, `!sheetstatus`, `!backfill_tickets`, `!backfill_details`, `!dedupe_sheet`, `!reload`, `!checksheet`, `!health`, `!reboot`, `!watch_status`, `!ping` (no role guards).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1022-L1279】
- **WelcomeCrew listeners & tasks**: slash sync hook, live thread watchers (`on_message`, `on_thread_update`), watchdog loop, scheduled tag refresh, socket heartbeat handlers.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L280-L1752】

## HTTP / External Endpoints
- **Matchmaker aiohttp server**: `GET /`, `/ready`, `/health` (shallow vs deep via `STRICT_PROBE`), `GET /healthz` (206 on zombie), `GET /emoji-pad` image proxy.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2303-L2495】
- **WelcomeCrew aiohttp server**: same health trio with optional deep probe plus `/healthz`; no emoji proxy.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1473-L1538】

## Google Sheets Operations
- **Matchmaker**: read-only scope (`spreadsheets.readonly`), cached `get_all_values()` for `bot_info`, recruiter summary parsing, and per-command pull of `WelcomeTemplates` via gspread client/worksheet fetch.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L166】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L660-L724】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- **WelcomeCrew**: service-account writer ensures headers for `Sheet1`/`Sheet4`, caches worksheet handles, reloads `clanlist`, throttles `append_row`/`update`, and retries transient failures via `_with_backoff`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L306-L520】
