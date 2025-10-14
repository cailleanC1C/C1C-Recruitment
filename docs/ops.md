# Operations

## Environment configuration
Set these variables in Render (or your hosting platform):

- `ADMIN_ROLE_ID` — Single numeric Discord role ID with admin access.
- `STAFF_ROLE_IDS` — Comma or space separated list of numeric staff role IDs.
- `KEEPALIVE_INTERVAL_SEC` — Default 360 in production, 60 in non-production.
- `WATCHDOG_STALL_SEC` — Optional; defaults based on keepalive interval when unset.
- `WATCHDOG_DISCONNECT_GRACE_SEC` — Optional; defaults to the stall interval.
- `BOT_VERSION` — Version string included in the help footer.
- `LOG_LEVEL` — Standard Python logging level (INFO recommended).
- `PORT` — Port exposed for the aiohttp health server.

## Discord intents
- Enable the Server Members intent in the Discord Developer Portal.
- Ensure `INTENTS.members = True` in code (already configured in `app.py`).
- Message Content intent must remain enabled so prefixes function.

## Deployment workflow
- GitHub Actions builds deploy artifacts and call `wait_render.js` to ensure
  a latest-wins release lane. In-flight deploys are canceled when a newer run arrives.
- Render services pull the latest image, set environment variables, and restart the bot
  on exit.

## Health and monitoring
- The aiohttp server exposes `/ready` for routing checks and `/healthz` for watchdog
  status.
- Watchdog logs include keepalive intervals, stall detections, reconnect attempts, and
  heartbeat latency snapshots. Monitor for repeated stall warnings or disconnect loops.

## RBAC troubleshooting
- Look for log entries showing resolved Admin and Staff role IDs during startup.
- Confirm incoming member payloads list the expected role IDs before a command executes.
- If commands silently drop, verify the member still carries an allowed role and that the
  Members intent is delivering updates.
