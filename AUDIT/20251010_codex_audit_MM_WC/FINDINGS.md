# Findings — Detailed Notes

## Duplicate & Near-Duplicate Segments (≥85% similarity)
| Area | Matchmaker anchor | WelcomeCrew anchor | Notes |
| --- | --- | --- | --- |
| Watchdog restart logic | `_watchdog` / `_maybe_restart`【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2261-L2297】 | `_watchdog` / `_maybe_restart`【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1433-L1471】 | Nearly identical loops (idle >600 s, latency >10s) and `sys.exit` restart path; refactorable into a shared helper. |
| Health endpoints | `_health_json*` + `STRICT_PROBE` routing【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2303-L2335】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2473-L2495】 | `_health_json*` + router wiring【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1473-L1538】 | Payload keys and route layout are line-for-line similar, differing only in uptime helper names. |
| Socket event bookkeeping | `on_socket_response/on_connect/on_resumed/on_ready`【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2162-L2205】 | Same quartet of events【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1398-L1430】 | Duplicated heartbeat tracking; candidates for a shared mixin. |

## Prior Review Findings Reconciliation
| ID | Summary | Status | Evidence |
| --- | --- | --- | --- |
| MM F-01 | Sheets fetch blocks event loop | **Present** | `get_rows()` still calls `ws.get_all_values()` synchronously on the main loop.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L123-L144】 |
| MM F-02 | Hard-coded welcome log channel | **Present** | `LOG_CHANNEL_ID = 1415330837968191629` remains in source.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2522】 |
| MM F-03 | Web server startup failures swallowed | **Present** | `asyncio.create_task(start_webserver())` fire-and-forgets without awaiting/guarding exceptions.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2530-L2537】 |
| WC F-01 | Prefix commands lack permission guards | **Present** | Commands (`!env_check` … `!watch_status`) have no role checks beyond env toggles.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1022-L1279】 |
| WC F-02 | Clan tag cache reload blocks gateway | **Present** | `_load_clan_tags()` still runs synchronous gspread calls invoked from message parsing paths.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L306-L354】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L622-L708】 |

## Permissions & Hard-Coded IDs
- Matchmaker relies on env-based role allow-lists but hard-codes the welcome log channel ID, forcing code edits for other guilds and exposing internal IDs in repositories/logs.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1100-L1148】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2500-L2522】 
- WelcomeCrew exposes powerful maintenance commands to any member when toggles are left ON; there is no guild-role enforcement or owner check beyond Discord’s inherent `Manage Guild` permission.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1022-L1279】 
- Both bots expect critical channel/thread IDs via environment variables; missing IDs only log to stdout (no DM/alert), so misconfigurations may go unnoticed.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L98-L108】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2140-L2156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L40-L83】

## Event-Loop Safety
- Matchmaker performs synchronous sheet reads (`get_all_values`) and template fetches on the gateway thread; under sheet slowness, panels and commands stall.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L123-L144】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- WelcomeCrew wraps several gspread calls with `_run_blocking`, but tag detection and portions of the watcher pipeline still hit gspread directly, risking 429 or latency cascades during cache misses.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L306-L354】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L622-L708】
- Both watchdogs call `sys.exit`/`os._exit` from async contexts; abrupt exits can skip aiohttp cleanup and risk partial writes if triggered during sheet operations.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2261-L2297】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1440-L1471】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1272-L1276】

## Google Sheets Read/Write Posture
- Matchmaker operates read-only (`spreadsheets.readonly` scope) against `bot_info`, caching rows for `CACHE_TTL` but re-authorizing the welcome sheet per request; there is no batching around recruiter summary reads.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L64-L166】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L660-L724】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2506-L2513】
- WelcomeCrew maintains worksheet caches, ensures headers for `Sheet1`/`Sheet4`, throttles `append_row`/`update` calls, and reuses `_with_backoff` to absorb transient 429/5xx responses; writes still occur serially per ticket.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L463-L520】
- Clan tag reloads power both bots (Matchmaker welcome Cog via shared sheet, WelcomeCrew watchers); caching alignment will be critical before merging to avoid duplicate sheet scans.【F:AUDIT/20251010_src/MM/welcome.py†L303-L406】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L306-L354】

## Health & Self-Ping Logic
- Both bots expose identical health JSON payloads (`ok`, `connected`, `uptime`, `last_event_age_s`, `latency_s`) with `/healthz` returning 206 when zombie heuristics trigger; `/`/`/ready` honor `STRICT_PROBE` for shallow vs deep checks.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2303-L2335】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2473-L2495】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1473-L1538】
- Matchmaker adds `!mmhealth` (text ping) plus `!ping` reactions, while WelcomeCrew mirrors `!ping` and offers `!health`; neither restricts HTTP health endpoints beyond network ACLs.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1799-L1808】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2054-L2082】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1098-L1252】
- Gateway activity timestamps are maintained via identical socket listeners; starvation of `_mark_event` will push both health endpoints into 206/503 responses simultaneously, underscoring the need for coordinated monitoring after merge.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2162-L2189】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1398-L1430】
