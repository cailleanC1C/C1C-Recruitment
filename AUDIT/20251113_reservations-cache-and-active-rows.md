## Context
The reservations flow collects recruiter input through `ReservationCog.reserve` and writes ledger rows via `shared.sheets.reservations.append_reservation_row`. The sheet recently gained a `ticket_username` display column plus a trailing `username_snapshot` field so the ledger can preserve both the recruiter-supplied username and the bot’s normalized snapshot that feeds AF/AH/AI recompute.

## Adapter & cache behavior
- **Append helper** — `shared/sheets/reservations.py::append_reservation_row` converts the supplied sequence to strings and calls `worksheet.append_row` on `RESERVATIONS_TAB`. It does **not** interact with `cache_service`; no reservation bucket exists, so only the worksheet is updated.
- **Ledger load** — `shared.sheets.reservations.load_reservation_ledger` refetches the entire sheet on every call by delegating to `_fetch_reservations_matrix` (a direct `async_core.afetch_values` call). Parsed rows are wrapped in `ReservationRow` objects and exposed through `_load_reservations`, so read paths always go back to the sheet.

## Active-row parsing
- `get_active_reservations_for_clan` normalizes the requested tag, pulls every row from `_load_reservations`, and filters where both `row.is_active` and `row.normalized_clan_tag` match.
- `ReservationRow.is_active` lowercases the status cell and requires the literal string `"active"`; other lifecycle strings (expired, cancelled, etc.) are ignored.
- `_build_header_index` resolves headers by alias, so each parsed field comes from the column whose header matches the legacy expectations. The adapter still expects the nine-column order written by the command: `thread_id`, `ticket_user_id`, `recruiter_id`, `clan_tag`, `reserved_until`, `created_at`, `status`, `notes`, `ticket_username`.
- **Current sheet order** (post username_snapshot rollout) now places `ticket_username` immediately after `ticket_user_id` and appends `username_snapshot` at the end:

  | Index | Header              | Written value today |
  |-------|---------------------|---------------------|
  | 0     | Thread ID           | `thread_id`
  | 1     | Ticket User ID      | `ticket_user_id`
  | 2     | Ticket Username     | **`recruiter_id` (mismatch)**
  | 3     | Recruiter ID        | **`clan_tag` (mismatch)**
  | 4     | Clan Tag            | **`reserved_until` (mismatch)**
  | 5     | Reserved Until      | **`created_at` (mismatch)**
  | 6     | Created At          | `status`
  | 7     | Status              | `notes`
  | 8     | Notes               | `ticket_username`
  | 9     | Username Snapshot   | *(blank — bot never writes column 10)*

  Because the adapter has no knowledge of the new column, every field from `recruiter_id` onward is read from the wrong cell when `_parse_reservation_row` runs.

## Root cause hypothesis — “0 reserved, 3 open”
1. `ReservationCog.reserve` still writes the legacy nine-value payload. The newly inserted `Ticket Username` column shifts subsequent cells one position to the right, so the `Clan Tag` header now points at the ISO `reserved_until` string.
2. During recompute, `reservations.get_active_reservations_for_clan` parses the row, normalizes `"2025-11-30"` to `"20251130"`, and compares it to the requested clan tag `"ABC"`. The normalized strings do not match, so the fresh reservation is filtered out.
3. `recompute_clan_availability` therefore sees `reservation_count = 0`, leaving AF/AH/AI unchanged despite the brand-new ledger row.

No cache invalidation is involved — the read helpers always hit the sheet — but the misaligned columns make the freshly appended row invisible to the clan-specific filter until staff manually reorders or copies the row.

## Non-goals
This PR records the adapter mismatch only. No runtime code has been changed to fix the column order or adjust cache behavior; follow-up work must correct the append logic and/or header parsing.
