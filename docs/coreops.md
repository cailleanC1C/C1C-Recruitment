# CoreOps Surface — Phase 2

CoreOps consolidates shared operational commands for the unified bot. All commands are available via `!rec <command>` or bot mention.

## Commands

| Command | Access | Description |
| --- | --- | --- |
| `!help` | All allowed guilds | Shows module overview, environment label, and contact footer. |
| `!ping` | All allowed guilds | Latency + heartbeat check; confirms gateway connectivity. |
| `!health` | Admin roles | Aggregates watchdog status, last refresh, and Config tab timestamps. |
| `!reload` | Admin roles | Forces Config tab re-read and sheet cache invalidation. |

> Legacy shortcuts (`!health`/`!env`/`!digest` split across bots) are retired. Phase 3b will revisit additional commands.

## Logging policy

- All command usage, success, and errors are emitted to `LOG_CHANNEL_ID`.
- Startup warnings include missing config keys, allow-list mismatches, and sheet load errors.
- Watchdog state transitions (stall, reconnect, grace exhausted) are logged at warning level.

## Watchdog controls

| Key | Default guidance |
| --- | --- |
| `WATCHDOG_CHECK_SEC` | 120s in prod, 60s elsewhere. Lower only when debugging stalls. |
| `WATCHDOG_STALL_SEC` | 240s in prod, 90s elsewhere. Must be > `WATCHDOG_CHECK_SEC`. |
| `WATCHDOG_DISCONNECT_GRACE_SEC` | 180s in prod, 60s elsewhere. Extends before gateway reconnect. |

Adjust values per environment with caution; aggressive settings increase false positives.

## Health surface

- HTTP `/ready` returns 200 once the bot has logged in and loaded Config tabs.
- HTTP `/healthz` returns 200 when the watchdog is healthy; 503 after consecutive stalls.
- `!health` command mirrors the same readiness info for Discord operators.
