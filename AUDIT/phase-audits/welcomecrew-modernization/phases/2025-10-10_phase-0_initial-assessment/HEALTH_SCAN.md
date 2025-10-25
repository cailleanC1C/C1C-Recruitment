# Health/self-ping Scan

AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/REVIEW/ARCH_MAP.md:10:7. **Logging & health** — Console logging plus optional thread notifications. HTTP health server exposes `/healthz` via aiohttp. Welcome cog logs to a fixed channel.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/REVIEW/REVIEW.md:69:**Issue.** The health-check server is started via `create_task` and the task is never awaited. If port binding fails (e.g., port already in use) the exception becomes an unobserved task error; the bot keeps running without `/healthz`, defeating watchdog/Render probes.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/REVIEW/TESTPLAN.md:11:9. **Health endpoints** — Curl `/`, `/ready`, `/healthz` with `STRICT_PROBE` on/off; confirm status codes adjust and emoji proxy enforces host allowlist.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/REVIEW/THREATS.md:7:- **Webhook / HTTP surface** — aiohttp server exposes health and emoji proxy endpoints reachable from the internet.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/requirements.txt:4:aiohttp>=3.9
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/.github/labels/labels.json:45:  { "name": "comp:ops-contract", "color": "6f42c1", "description": "Ops parity: ping/health/digest/reload" },
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/README.md:23:* **Health + tiny web server**: `/health`, `/ready`, `/healthz` and `/emoji-pad` (proxy that pads/centers emoji images).
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/README.md:102:* `STRICT_PROBE` — `1` to make `/` and `/ready` return deep health (200/206/503). Default `0` (always 200; use `/healthz` for deep).
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/README.md:171:   pip install discord.py gspread google-auth aiohttp pillow
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/README.md:233:* `/healthz`: deep JSON health (200 when connected; 503 when disconnected; 206 if “zombie-ish”).
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:16:from aiohttp import web, ClientSession, ClientTimeout
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:45:# If 0 (default), `/` and `/ready` always return 200 while `/healthz` is the deep check.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:2473:# - When STRICT_PROBE=0 (default): `/`, `/ready`, `/health` always 200
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:2478:        app.router.add_get("/health", _health_json)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:2482:        app.router.add_get("/health", _health_json_ok_always)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:2485:    app.router.add_get("/healthz", _health_json)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py:2495:    print(f"[keepalive] HTTP server listening on :{port} | STRICT_PROBE={int(STRICT_PROBE)}", flush=True)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/REVIEW/ARCH_MAP.md:9:6. **Keepalive** — An aiohttp web server provides `/healthz`, while a scheduled refresh task (`scheduled_refresh_loop`) reloads clan tags three times per day.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/REVIEW/THREATS.md:7:- **Render deployment** — Hosts aiohttp health endpoints and long-lived Discord session.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/requirements.txt:4:aiohttp>=3.9
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/.github/labels/labels.json:45:  { "name": "comp:ops-contract", "color": "6f42c1", "description": "Ops parity: ping/health/digest/reload" },
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/README.md:15:* **Health & watchdog**: `/healthz` endpoint + a watchdog that restarts the process if the gateway looks “zombied”.
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/README.md:25:   * `discord.py`, `gspread`, `google-auth`, `aiohttp`
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/README.md:28:   pip install discord.py gspread google-auth aiohttp
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/README.md:131:  * `/healthz` always returns deep status (200/206/503).
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:27:from aiohttp import web, ClientSession
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:669:# ---- keepalive / watchdog state ----
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:1524:        app.router.add_get("/health", _health_json)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:1528:        app.router.add_get("/health", _health_json_ok_always)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:1531:    app.router.add_get("/healthz", _health_json)
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py:1538:    print(f"[keepalive] HTTP server on :{port} | STRICT_PROBE={int(STRICT_PROBE)}", flush=True)

Doc last updated: 2025-10-10 (v0.9.5)
