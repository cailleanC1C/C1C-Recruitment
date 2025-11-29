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
- Lifecycle logs surface as `Promo panel — scope=promo` entries; welcome only
  handles threads that begin with `W####-…`.

## Configuration

- **Channels:** `PROMO_CHANNEL_ID`
- **Sheet tab:** `PROMO_TICKETS_TAB`
- **Toggles:** `PROMO_ENABLED`, `ENABLE_PROMO_HOOK` (promo dialog toggle
  reserved for later: `promo_dialog`)

## Onboarding hooks

- Ticket Tool greetings in promo threads must retain the hidden trigger line at
  the bottom of the template:
  - `<!-- trigger:promo.r -->` — Returning Player
  - `<!-- trigger:promo.m -->` — Member / Player Move Request
  - `<!-- trigger:promo.l -->` — Leadership Move Request
- When `PROMO_ENABLED` and `ENABLE_PROMO_HOOK` are on, the bot reacts to the
  trigger, posts the Open Questions panel, and launches the corresponding promo
  flow when the panel is opened.
- Recruiters can also add 🎫 to the Ticket Tool greeting to surface the panel if
  the watcher misses the trigger. Removing the trigger lines prevents the bot
  from recognising promo tickets.

Doc last updated: 2025-11-29 (v0.9.7)
