# Reservations & Availability Wiring — Audit (2025-11-13)

## Context
Recruitment staff use the `!reserve` command to hold seats for recruits. The bot stores reservations in the `RESERVATIONS_TAB` worksheet and mirrors clan availability in `CLANS_TAB` (a.k.a. `bot_info`), where columns AF/AH/AI track manual open spots, reserved counts, and reservation summaries.

## Findings — Command implementation
- **Command handler**: `modules/placement/reservations.py::ReservationCog.reserve`
  - Prefix command registered via `@commands.command(name="reserve")` with staff-tier help metadata.
  - Gated by feature toggles (`FEATURE_RESERVATIONS` / aliases) and RBAC checks (`is_recruiter` or `is_admin_member`). Only allowed inside ticket threads whose parent matches `get_welcome_channel_id` / `get_promo_channel_id`.
  - Accepts `<clantag>` argument; normalized by `_normalize_tag` when validating the sheet lookup.
- **Clan lookup**: `shared.sheets.recruitment.find_clan_row`
  - Reads `CLANS_TAB` to retrieve the manual open count (column E) before starting the interactive flow.
- **Interactive flow**: `ReservationConversation`
  - Prompts the recruiter for the recruit mention/ID, reservation end date (`YYYY-MM-DD`), and (when effective spots ≤ 0) a reason note.
  - Uses the pre-fetched manual open value and `reservations.count_active_reservations_for_clan` to show live availability and decide whether a reason is required.
- **Ledger write**: after confirmation, composes a 9-column row of strings and calls `shared.sheets.reservations.append_reservation_row` to append to `RESERVATIONS_TAB`:
  1. Ticket thread ID
  2. Recruit (Discord user ID)
  3. Recruiter ID
  4. Clan tag (sheet tag)
  5. `reserved_until` date (ISO)
  6. Creation timestamp (`now` UTC, ISO)
  7. Status = `"active"`
  8. Free-form notes
  9. Recruit username snapshot
- **Post-write refresh**:
  - Calls `modules.recruitment.availability.recompute_clan_availability(sheet_tag, guild=ctx.guild)`.
  - Falls back to cached manual values if the recompute helper fails, but still logs and informs staff.
  - Reloads the clan row via `shared.sheets.recruitment.get_clan_by_tag` to report the updated AF/AH figures back into the ticket thread log message.

## Findings — Availability recompute
- **Helper location**: `modules/recruitment/availability.py::recompute_clan_availability`
  - Fetches the clan row (`find_clan_row`) and parses column E (`_parse_manual_open_spots`) as the manual open spot count.
  - Loads active reservations through `shared.sheets.reservations.get_active_reservations_for_clan` and resolves display names with `resolve_reservation_names` (guild or custom resolver context).
  - Calculates:
    - `reservation_count = len(active_reservations)` → written to column AH.
    - `available_after_reservations = max(manual_open - reservation_count, 0)` → written to column AF.
    - `reservation_summary = "{count} -> ..."` with resolved usernames → written to column AI.
  - Preserves the current AG (“inactives”) value while overwriting the AF–AI block in a single `worksheet.update("AF{row}:AI{row}", ...)` call via `async_core.acall_with_backoff`.
  - Updates in-memory caches with `shared.sheets.recruitment.update_cached_clan_row`, ensuring subsequent lookups see the refreshed AF/AH/AI.
- **Callers**:
  - `!reserve` (above) triggers it immediately after appending the ledger row.
  - Reservation cron jobs (`modules/placement/reservation_jobs.reservations_reminder_daily` and `.reservations_autorelease_daily`) invoke it for each affected clan when reminding or expiring holds.

## Mismatches vs Spec
- None observed. The live implementation already recalculates AF/AH/AI from column E and active reservations, writes the results back to `CLANS_TAB`, and refreshes caches whenever `!reserve` or the reservation jobs mutate the ledger.

## Non-goals
No runtime behavior changes were made in this audit. Findings are provided for follow-up work as needed.
