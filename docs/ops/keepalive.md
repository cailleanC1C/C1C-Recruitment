# Keep-Alive (Render)

- Route: `GET /keepalive` → `200 ok`
- URL resolution:
  1) `KEEPALIVE_URL` (explicit)
  2) `RENDER_EXTERNAL_URL` + `KEEPALIVE_PATH` (defaults to `/keepalive`)
- Interval: `KEEPALIVE_INTERVAL` seconds (min 60, default 300)

## Verify
- Look for logs: `keepalive:task_started`, then periodic `keepalive:ping_ok`.

## Troubleshooting
- No logs? Ready hook didn’t call `ensure_started()`. Confirm post-ready path.
- Non-200? Hit the public URL in a browser; route must return 200.
- Wrong host? Set `KEEPALIVE_URL` explicitly.

## Env / Config
No hard-coded values. Uses KEEPALIVE_URL | RENDER_EXTERNAL_URL + KEEPALIVE_PATH | local dev fallback.

`KEEPALIVE_INTERVAL` (seconds) optional, defaults 300, never below 60.

## Testing
Manual: Watch logs for keepalive:task_started, then keepalive:ping_ok every interval.

Render: Confirm service no longer idles; cron logs continue at scheduled times.

Local: Run server; curl http://localhost:PORT/keepalive returns ok.

Doc last updated: 2025-11-11 (v0.9.7)
