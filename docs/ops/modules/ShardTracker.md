# Shard & Mercy Tracker Module

Community-focused module that lets members maintain their RAID shard stash and
legendary pity counters directly in Discord. Every interaction happens inside
the dedicated **Shards & Mercy** channel so global chatter stays clean while
users keep a personal, button-driven tracker thread.

## Scope & Responsibilities

- Persist shard stash counts plus pity counters (`ancient`, `void`, `sacred`,
  `primal`, and the primal-mythic pity) per Discord user.
- Enforce channel routing: only the configured Shards & Mercy channel may run
  shard commands, and every user gets a private thread underneath that channel.
- Surface a mobile-friendly embed with buttons so players can log pulls or add
  shards without typing commands.
- Provide reset commands (`!lego`, `!mythic primal`) plus manual setters for
  stash (`!shards set …`) and mercy (`!mercy set …`).
- Log lifecycle, warning, and error states through the existing C1C log helper
  plus ADMIN_ROLE_IDS pings on hard failures.

> Cleanup/auto-archive of shard threads is handled in a follow-up PR. This
> module only creates and reuses per-user threads; they persist indefinitely
> today.

## Storage & Configuration

- **Sheet:** `MILESTONES_SHEET_ID` (service account credentials already live in
  `GSPREAD_CREDENTIALS`).
- **Config tab:** `MILESTONES_CONFIG_TAB` (defaults to `Config`). Required keys:
  - `SHARD_MERCY_TAB` — worksheet name that stores shard rows.
  - `SHARD_MERCY_CHANNEL_ID` — numeric ID for the dedicated Discord channel.
- **Worksheet schema:** row 1 contains the canonical headers listed below.
  `discord_id` is the primary key and all headers must remain in this order.

| Column | Purpose |
| --- | --- |
| `discord_id` | Snowflake ID for the Discord user. |
| `username_snapshot` | Last display name captured when the bot touched the row. |
| `ancients_owned`, `voids_owned`, `sacreds_owned`, `primals_owned` | Current stash counts. |
| `ancients_since_lego`, `voids_since_lego`, `sacreds_since_lego`, `primals_since_lego` | Mercy counters per shard type. |
| `primals_since_mythic` | Mythic pity counter. |
| `last_*_lego_iso`, `last_primal_mythic_iso`, `last_updated_iso` | UTC ISO timestamps for the last logged LEGO/mythic and update time. |

Rows are created automatically the first time a user opens the tracker; all
fields initialize to zero and timestamps stay blank until a LEGO is recorded.

## Mercy Math Reference

| Type | Base chance | Mercy threshold | Increment | Guarantee |
| --- | --- | --- | --- | --- |
| Ancient | 0.5% | 200 shards | +0.5% per shard | 220th shard |
| Void | 0.5% | 200 shards | +0.5% per shard | 220th shard |
| Sacred | 6% | 12 shards | +2% per shard | 20th shard |
| Primal (Legendary) | 100% | Immediate | — | Every shard |
| Primal Mythic | 10% | 10 shards | +2% per shard | 20th shard |

Ancient/Void/Sacred counters increase once you cross the threshold (e.g., the
201st Ancient shard applies the first +0.5% bonus). Primal Legendary drops are
always guaranteed; we still track the counter for visibility. Primal mythic pity
uses the dedicated counter and only resets when `!mythic primal` is logged.

## Commands & Buttons

| Command | Notes |
| --- | --- |
| `!shards [type]` | Posts the stash + mercy dashboard in the user’s shard thread. Optional `type` renders a focused card. |
| `!shards set <type> <count>` | Force-set a stash count (non-negative integer). |
| `!mercy [type]` | Same routing as `!shards`; primarily a help alias. |
| `!mercy set <type> <count>` | Override a mercy counter. Accepts `mythic` for the primal-mythic pity. |
| `!lego <type> [after_count]` | Reset a mercy counter when a LEGO drops. `after_count` captures shards pulled after the LEGO before logging (defaults to `0`). |
| `!mythic primal [after_count]` | Reset both primal counters when a mythic drops. |

All commands **must** be issued in `<#SHARD_MERCY_CHANNEL_ID>`. When a member
runs a command directly in that channel, the bot creates (or reuses) their
personal thread named `Shards – <Display Name> [user_id]`, posts the embed
there, and replies in the parent channel with a short pointer.

Buttons live on every embed inside the user’s thread:

- **Add <type>** — increments the stash count for that shard type.
- **Pull <type>** — decrements the stash (clamped at zero) and increments the
  mercy counters (`primal` pulls also bump the mythic pity).

Only the thread owner may press the buttons; everyone else receives a friendly
rejection message. Button handlers write through to Sheets immediately and edit
the message in place.

## Thread Workflow

1. **First use:** the member types `!shards` in the configured channel. The bot
   creates a private thread, posts the dashboard there, and mentions the user in
   the parent channel with a “📬 Posted in your shard thread” pointer.
2. **Returning users:** commands or buttons run inside the thread directly, or
   the user can type another command in the parent channel; the bot replies in
   the existing thread to keep the parent channel clean.
3. **Finding the thread later:** the channel’s thread list shows
   `Shards – <Display Name> [user_id]`. Members can also re-run `!shards` in the
   parent channel; the bot links the thread again instead of duplicating it.

## Logging & Errors

- Lifecycle events (`📘 Shards — …`) post via `runtime.send_log_message`. Each
  action includes the user label plus a concise description.
- Hard errors (missing config tab, header mismatch, invalid channel) reply to
  the user with a polite explanation and ping the first ADMIN_ROLE_ID inside a
  `❌` log entry.
- All Sheets writes run through the shared async backoff helper and use a
  single-row range update (`A{row}:Q{row}`) so the schema stays intact.

## Testing Expectations

Automated tests cover:

- Mercy math for every shard type and the primal mythic pity.
- Sheet mapping (row ↔ dataclass) to ensure headers remain stable.
- Command parsing helpers (`type` aliases, channel gating).
- Thread routing unit tests verifying channel restrictions and reusing an
  existing thread before creating a new one.

Doc last updated: 2025-11-18 (v0.9.7)

