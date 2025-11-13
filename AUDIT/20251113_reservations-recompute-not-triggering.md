## Context
The `!reserve` command (Discord staff-only) is implemented in `modules/placement/reservations.py` and writes rows into the `RESERVATIONS_TAB` worksheet. Immediately after the append it calls `modules.recruitment.availability.recompute_clan_availability` to recalculate the `AF`/`AG`/`AH`/`AI` slice within `CLANS_TAB`. Runtime reports indicate that fresh reservations never change those cells, and the bot produces no availability logs.

## Helper implementation: `recompute_clan_availability`
- **Location** — `modules/recruitment/availability.py::recompute_clan_availability(clan_tag: str, *, guild=None, resolver=None)`.
- **Dependencies** — Reads the clan row through `shared.sheets.recruitment.find_clan_row`, fetches reservations via `shared.sheets.reservations.get_active_reservations_for_clan`, resolves names with `reservations.resolve_reservation_names`, then writes back to Sheets using `shared.sheets.async_core.acall_with_backoff`.
- **Side effects** — Updates `AF{row}:AI{row}` in `CLANS_TAB`, refreshes the in-memory clan cache through `recruitment.update_cached_clan_row`, and emits a `log.debug("recomputed clan availability", extra=...)` entry.

## Command call site and gating
- **Call path** — `ReservationCog.reserve` lives in `modules/placement/reservations.py`. After collecting inputs and appending the ledger row it executes `await availability.recompute_clan_availability(sheet_tag, guild=ctx.guild)` inside a try/except block that only logs on failure.
- **Feature flag** — `_reservations_enabled()` iterates over `("FEATURE_RESERVATIONS", "feature_reservations", "placement_reservations")` and returns `True` as soon as `modules.common.feature_flags.is_enabled` reports a truthy toggle.
- **RBAC** — The command returns early unless the invoker satisfies `is_recruiter(ctx)` or `is_admin_member(ctx)`; these checks do not guard the recompute branch once the flow passes validation.
- **Early exits** — Prior to recompute the only returns come from validation, conversation abort, or append failure. On success the recompute call always executes.

## Runtime flow after appending to the ledger
```
append_reservation_row([...])  # writes 9 legacy fields
recompute_clan_availability(sheet_tag, guild=ctx.guild)
```
- The append helper stringifies the payload and calls `worksheet.append_row` directly. There is no cache to invalidate, and subsequent reads go back to the sheet.
- The recompute call is not conditional beyond the surrounding try/except; no feature flag or RBAC guard is re-checked in that block, and no silent `return` statements intervene.
- If recompute were to raise, the command would log an exception and post a warning into the ticket thread. Runtime reports never mentioned that warning, implying the call does not throw.

## Logging behavior within recompute
- The helper only uses `log.debug`, so production log levels (`INFO` by default) will not surface availability recompute lines.
- No other logger invocations occur before the sheet update completes. If the helper returns normally the only visible log is the final `log.info("[reserve] reservation created", ...)` emitted by the command.

## Sheet update path
- `recompute_clan_availability` writes `[available_after_reservations, existing_AG, reservation_count, reservation_summary]` to `AF{row}:AI{row}` on the worksheet obtained from `recruitment.get_clans_tab_name()`.
- The update is wrapped in `async_core.acall_with_backoff`, so gspread/network errors would bubble as exceptions (triggering the command’s warning branch). There is no suppression of failures.
- Immediately after writing, `recruitment.update_cached_clan_row` mutates the cached clan list so future reads observe the new AF/AH/AI values without another sheet fetch.

## Reservation filtering and why the helper sees zero rows
- `append_reservation_row` still sends the legacy nine-value payload (`thread_id` through `ticket_username`).
- The reservations worksheet now includes a tenth column (`Username Snapshot`) immediately after `Ticket Username`.
- When Sheets inserts the new column, every subsequent field shifts one position to the right, but `_HEADER_ALIASES` still maps `"clan tag"` to index 4.
- `_parse_reservation_row` therefore reads the ISO reserved-until string (e.g., `2025-11-30`) as the clan tag. `_normalize_tag` strips non-alphanumerics and uppercases, producing `20251130`.
- `ReservationRow.normalized_clan_tag` returns `20251130`, so `get_active_reservations_for_clan("ABC")` filters the fresh row out. With zero matches, `recompute_clan_availability` calculates `reservation_count = 0` and leaves AF/AH/AI unchanged.

## Feature toggles and runtime state
- Feature toggles load via `modules/common/feature_flags.py`. Once `FEATURE_RESERVATIONS` is set to `TRUE`, `_reservations_enabled()` returns `True`, the command executes, and the recompute helper is still invoked regardless of toggle state at the moment of append.
- If the toggle is missing or false, the command stops before prompting the recruiter, so no ledger row is appended in the failing scenario described by ops (confirming the feature flag is not responsible for the mismatch).

## Root cause
The recompute helper *does* run, but it reads stale clan-tag values because the worksheet header gained an extra column without updating either the append payload or the parser’s header map. As a result, new rows appear under the wrong clan during filtering, so availability math continues to assume zero active reservations. No exceptions are thrown, and the helper’s debug-only logging keeps runtime telemetry silent even though recompute finishes.

## Non-goals
This audit documents the live behavior only. No code changes were attempted to realign the reservation payload, extend header aliases, or elevate logging levels.
