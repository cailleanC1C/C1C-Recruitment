# Core Infra Contract (Phase 1)

/healthz fields:
- env (string: "test" | "prod")
- connected (boolean)
- uptime_s (integer)
- last_event_age_s (integer)

Watchdog:
- Restart when last_event_age_s > WATCHDOG_RESTART_GRACE_S
- Shutdown order: Discord -> aiohttp -> exit
