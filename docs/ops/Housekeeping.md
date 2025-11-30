# Housekeeping jobs

Housekeeping centralizes recurring maintenance tasks that keep panel threads clean
and long-lived threads active without manual nudges.

## Cleanup
- **Scope.** Deletes every non-pinned message in configured threads so panels reset
  each run. Pinned messages are never removed.
- **Cadence.** Runs every `CLEANUP_INTERVAL_HOURS` (default: 24h).
- **Targets.** Threads enumerated via `CLEANUP_THREAD_IDS`.
- **Logging.** One summary line per run:
  - `🧹 Cleanup — threads=<N> • messages_deleted=<M> • errors=<E>`
- **Error handling.** Missing permissions or API failures are logged as WARN lines
  and counted in the `errors` field, but the job continues to the next thread.

## Thread keepalive
- **Purpose.** Prevents important threads from auto-archiving when idle.
- **Cadence.** Runs hourly and acts only when the last activity is older than
  `KEEPALIVE_INTERVAL_HOURS` (default: 144h).
- **Targets.**
  - All threads (active + archived) inside channels listed in `KEEPALIVE_CHANNEL_IDS`.
  - Explicit thread IDs in `KEEPALIVE_THREAD_IDS`.
- **Behavior.** Deduplicates targets, checks read/send/manage-thread permissions,
  unarchives stale threads, and posts the heartbeat message
  `🔹 Thread 💙-beat (housekeeping)`.
- **Logging.** Summary per run:
  - `💙 Housekeeping: keepalive — threads_touched=<N> • errors=<E>`
  WARN lines capture fetch, unarchive, or send failures without blocking later
  targets.

## Future additions
AutoMod/Guardian Knight bridging will land in this module in a future phase to
keep moderation actions aligned with housekeeping cadences.

Doc last updated: 2025-11-30 (v0.9.8.1)
