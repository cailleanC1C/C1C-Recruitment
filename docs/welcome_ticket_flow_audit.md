# Welcome ticket flow audit

## Manual closes and manual fallback
- Manual fallback closes that set a final clan now insert a missing onboarding row when needed and still run the same reconciliation path as automated closes.
- When the final clan is set for the first time (including after a manual fallback), the placement consumes a clan seat even if there was no reservation tied to the ticket.
- Manual closes continue to emit both the `welcome_close_manual` event (with reason + action) and the `onboarding_finalize_reconcile` summary for the row and clan results.

## Reserve and placement behavior
- If `rename_thread_to_reserved` cannot parse the ticket from a thread name (for example, malformed prefixes like `W554-...`), the bot now raises a ❌ `welcome_reserve_rename_error` log at ERROR level.
- A human-facing ❌ log is also sent to ping admin roles with the tag, thread name, and parse failure reason so the thread can be corrected manually.

Doc last updated: 2025-11-29 (v0.9.7)
