# Config knobs — Unified keepalive/watchdog

| Env var | Default | When to change | Notes |
| --- | --- | --- | --- |
| `KEEPALIVE_INTERVAL_SEC` | Prod-like envs → `360`; dev/test/stage → `60` | Adjust the watchdog poll cadence (Render free tier may need shorter if networking is flaky). | Maps directly to the watchdog `check_every` interval. Must remain between 60–600s for prod as per requirement. |
| `WATCHDOG_STALL_SEC` | Derived `keepalive * 3 + 30` (e.g. prod default `1110`) | Force a different zombie threshold. | Mirrors the legacy heuristic of "3× interval + 30s"; override when traffic patterns demand faster restarts. |
| `WATCHDOG_DISCONNECT_GRACE_SEC` | Defaults to the stall threshold. | Tune tolerance for prolonged disconnects independently of zombie detection. | If unset, disconnect and zombie limits are the same. |
| `ENV_NAME` | `dev` | Tag deployment environment. | Drives the keepalive defaults above (values other than `dev/development/test/qa/stage` treated as prod). |
| `COMMAND_PREFIX` | `rec` | Adjust bang commands. | No change for keepalive but included for completeness. |
| `PORT` | `10000` (unless `$PORT` from Render) | Change health server bind port. | Health endpoints `/ready` + `/healthz` continue to rely on the heartbeat timestamps. |

## Relationships
- Stall + disconnect grace recompute automatically when `KEEPALIVE_INTERVAL_SEC` changes, keeping the 3×+30 buffer intact.
- Overrides always win; invalid override values fall back to the computed defaults.

## Operational guidance
- For QA/staging smoke tests set `ENV_NAME=stage` (or explicit `KEEPALIVE_INTERVAL_SEC=60`) to keep quick watchdog loops.
- Avoid setting keepalive below 30s — Render free tier can starve the loop; prefer ≥60s except when debugging locally.
