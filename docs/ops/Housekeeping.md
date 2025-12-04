# Housekeeping jobs

Housekeeping centralizes recurring maintenance tasks that keep panel threads clean
and long-lived threads active without manual nudges.

- Feature toggles: `housekeeping_enabled` gates cleanup/keepalive scheduling; `mirralith_overview_enabled` also guards Mirralith overview posting.

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

## Role & Visitor audit
- **Purpose.** Realigns members with the expected Raid/Clan/Wandering role
  combinations and highlights Visitor records that have stalled.
- **Inputs.** `RAID_ROLE_ID`, `WANDERING_SOULS_ROLE_ID`, `VISITOR_ROLE_ID`,
  `CLAN_ROLE_IDS`, `ADMIN_AUDIT_DEST_ID`, and ticket channels
  (`WELCOME_CHANNEL_ID`, `PROMO_CHANNEL_ID`).
- **Auto-fixes.**
  - Removes Raid and adds Wandering Souls when a member has no clan tags.
  - Removes Raid from existing Wanderers that lost their clan tags.
- **Reports only.**
  - Wandering Souls that still carry clan tags.
  - Visitors without tickets, with only closed tickets, or with extra roles.
- **Delivery.** Posts one consolidated message per run to
  `ADMIN_AUDIT_DEST_ID` with section headings for each bucket.

## Future additions
AutoMod/Guardian Knight bridging will land in this module in a future phase to
keep moderation actions aligned with housekeeping cadences.

Doc last updated: 2025-12-03 (v0.9.8.2)
