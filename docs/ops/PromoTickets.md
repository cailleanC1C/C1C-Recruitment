# Promo tickets

Promo tickets track returning players and clan move requests. Ticket Tool names
follow the `R/M/L` prefix patterns:

- `R####-username` — returning player tickets
- `M####-username` — member/player move requests
- `L####-username` — clan lead move requests

Optional clan tags may trail the username (e.g., `R0123-user-CLAN`).

## Logging

The promo watcher (`modules.onboarding.watcher_promo.PromoTicketWatcher`):

- Detects threads under `PROMO_CHANNEL_ID` without checking thread owners.
- Parses promo ticket names to extract `ticket number`, `username`, and optional
  `clantag`.
- Logs opens and closes to the `PROMO_TICKETS_TAB` worksheet using the following
  columns:

  `ticket number | username | clantag | date closed | type | thread created |
  year | month | join_month | clan name | progression`

- Maps prefixes to types: `R` → `returning player`, `M` → `player move request`,
  `L` → `clan lead move request`.
- On closure, prompts for a clan tag and progression text; responses update the
  `clantag`, `date closed`, `clan name`, and `progression` fields. Dialog/panel
  onboarding for promo tickets will arrive in a later release.

## Configuration

- **Channels:** `PROMO_CHANNEL_ID`
- **Sheet tab:** `PROMO_TICKETS_TAB`
- **Toggles:** `PROMO_ENABLED`, `ENABLE_PROMO_HOOK` (promo dialog toggle
  reserved for later: `promo_dialog`)

Doc last updated: 2025-11-24 (v0.9.7)
