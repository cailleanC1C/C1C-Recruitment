# Core Infra Contract (Phase 1)

## Scope
Infra must provide reliable runtime, deployment, and observability surfaces while the bot guarantees readiness probes, watchdog exits, and structured logging consistent with Phase 1 behavior.

## Inputs (Env / Secrets)
- `DISCORD_TOKEN` (required)
- `ADMIN_ROLE_ID` (single numeric)
- `STAFF_ROLE_IDS` (comma/space numeric)
- `KEEPALIVE_INTERVAL_SEC` (prod default 360; non-prod 60)
- `WATCHDOG_STALL_SEC` (defaults to keepalive*3+30 if unset)
- `WATCHDOG_DISCONNECT_GRACE_SEC` (defaults to stall)
- `BOT_VERSION` (optional)
- `LOG_LEVEL` (optional)
- `PORT` (Render-provided)

## Intents / Permissions
- Dev Portal: enable **Server Members Intent** and **Message Content**.
- Code: `INTENTS.members=True`, `INTENTS.message_content=True`.

## Network / Health
- HTTP server (aiohttp) with:
  - `/ready`: returns 200 once server is up.
  - `/healthz`: returns 200 if heartbeat age <= stall; else 503.
- Single container instance; process exit triggers platform restart.

## Watchdog & Heartbeat
- Heartbeat source: gateway events (connect/ready/socket receive).
- Config:
  - check interval = `KEEPALIVE_INTERVAL_SEC`
  - stall = `WATCHDOG_STALL_SEC` (or derived)
  - disconnect grace = `WATCHDOG_DISCONNECT_GRACE_SEC` (or stall)
- Exit conditions:
  - Connected but zombie (age > stall) and latency missing/poor → `exit(1)`
  - Disconnected for > disconnect grace → `exit(1)`

## Command Routing & Prefix
- Supported: `!rec`, `!rec␣`, `rec`, `rec␣`, `@mention`.
- Admin bang shortcuts: `!health|!env|!digest|!help` (Admin role only).
- No bare-word shortcuts.

## RBAC (Role-based)
- Staff gate = Admin role OR any Staff role.
- Admin-only actions (e.g., bang shortcuts).
- No user-ID gating.

## Logging
- Level via `LOG_LEVEL` (default INFO).
- Startup confirms parsed role IDs.
- Logs heartbeat/watchdog decisions and command errors.

## CI/CD
- GitHub Actions workflow: queued, latest-wins lane with cancel (`wait_render.js`).
- Render deploy via hook; container builds with Dockerfile; Python 3.12.

## SLO-ish Expectations
- Ready within ~10s after container up.
- Auto-recover on gateway stalls/disconnects via watchdog exit+restart.
- Low chat noise; background-first.

## Change Management
- Backwards-compatible env keys; no behavior changes without CHANGELOG entry.
- Timezone in help footer: Europe/Vienna with UTC fallback.
