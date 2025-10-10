# Health/self-ping Scan

work/Achievements/.github/labels/harmonized.json:45:  { "name": "comp:ops-contract", "color": "6f42c1", "description": "Ops parity: ping/health/digest/reload" },
work/Achievements/docs/DEVELOPMENT.md:9:* **Service bootstrap**: `c1c_claims_appreciation.py` — bot init, Flask keep-alive, config loader (Sheets or local), watchdog/health wiring, Cog registration.
work/Achievements/c1c_claims_appreciation.py:13:from aiohttp import ClientConnectorError
work/WelcomeCrew/REVIEW/ARCH_MAP.md:9:6. **Keepalive** — An aiohttp web server provides `/healthz`, while a scheduled refresh task (`scheduled_refresh_loop`) reloads clan tags three times per day.
work/WelcomeCrew/REVIEW/THREATS.md:7:- **Render deployment** — Hosts aiohttp health endpoints and long-lived Discord session.
work/WelcomeCrew/requirements.txt:4:aiohttp>=3.9
work/WelcomeCrew/.github/labels/labels.json:45:  { "name": "comp:ops-contract", "color": "6f42c1", "description": "Ops parity: ping/health/digest/reload" },
work/WelcomeCrew/README.md:15:* **Health & watchdog**: `/healthz` endpoint + a watchdog that restarts the process if the gateway looks “zombied”.
work/WelcomeCrew/README.md:25:   * `discord.py`, `gspread`, `google-auth`, `aiohttp`
work/WelcomeCrew/README.md:28:   pip install discord.py gspread google-auth aiohttp
work/WelcomeCrew/README.md:131:  * `/healthz` always returns deep status (200/206/503).
work/WelcomeCrew/bot_welcomecrew.py:27:from aiohttp import web, ClientSession
work/WelcomeCrew/bot_welcomecrew.py:669:# ---- keepalive / watchdog state ----
work/WelcomeCrew/bot_welcomecrew.py:1524:        app.router.add_get("/health", _health_json)
work/WelcomeCrew/bot_welcomecrew.py:1528:        app.router.add_get("/health", _health_json_ok_always)
work/WelcomeCrew/bot_welcomecrew.py:1531:    app.router.add_get("/healthz", _health_json)
work/WelcomeCrew/bot_welcomecrew.py:1538:    print(f"[keepalive] HTTP server on :{port} | STRICT_PROBE={int(STRICT_PROBE)}", flush=True)
