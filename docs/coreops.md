# Core Ops (Phase 2)

## Commands (Phase 2)
- `!help`, `!ping`, `!health`, `!reload` — shared core.
- `!welcome`, `!welcome-*` — staff-gated. Present but not wired to Sheets until Phase 3.
- Watchers present but Sheets wiring lands in Phase 3.

## Logging
All confirmations and error logs → `LOG_CHANNEL_ID` (#bot-production).

## Watchdog
- `WATCHDOG_CHECK_SEC` — check cadence.
- `WATCHDOG_STALL_SEC` — restart if no events while connected.
- `WATCHDOG_DISCONNECT_GRACE_SEC` — restart after prolonged disconnect.

## Allow-list
Bot aborts if active guild not in `GUILD_IDS`.
