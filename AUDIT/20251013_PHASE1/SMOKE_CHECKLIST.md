# Smoke checklist — Keepalive/Watchdog port

## Pre-flight
- [ ] Set `ENV_NAME` and (optionally) overrides for keepalive/stall; confirm Render free tier dyno has access to `/ready`.
- [ ] Ensure `DISCORD_TOKEN` is configured so the bot can reach READY.

## Bring-up
1. `python app.py` (or container entrypoint) — wait for logs:
   - `Watchdog started (stall_after=... interval=... disconnect_grace=...)`
   - `Bot ready as ...`
2. Confirm background loop logs continue without errors for at least one keepalive interval.

## HTTP probes
- [ ] `curl -fsS localhost:$PORT/ready` returns `ok`.
- [ ] `curl -fsS localhost:$PORT/healthz | jq` shows `"ok": true` with `age_seconds` <= stall threshold.
- [ ] Simulate disconnect (kill network or `discord.gateway` patch) and verify `/healthz` flips to HTTP 503 when `connected` becomes false.

## Watchdog behaviour
- [ ] While connected, block gateway events (e.g., intercept websocket) until `age_seconds` exceeds stall — watchdog should log zombie exit (latency None/>10) and process terminates.
- [ ] Force a disconnect longer than `WATCHDOG_DISCONNECT_GRACE_SEC` and confirm watchdog exits with `disconnected for ...` log.
- [ ] Validate logs flush before exit (no truncated watchdog message).

## Post-check
- [ ] After restart, confirm keepalive metrics reset: `age_seconds` near 0, `/healthz` returns 200.
- [ ] Review Render logs to ensure restart loop stops once gateway is stable.
