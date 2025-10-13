# Admin Bang Shortcuts – Phase 1 Notes

## Rationale
- Ensure admin shortcuts reuse the dispatcher instead of cloning messages.
- Harden role ID parsing so legacy `.env` formats keep working without manual cleanup.

## Changes
- Added RBAC startup log showing the parsed Admin role ID and Staff role IDs.
- Updated `detect_admin_bang_command` to normalize command names and return dispatcher-ready names for Admin-only bang shortcuts.
- Switched Admin bang handling in `on_message` to use `bot.invoke` with the resolved context.
- Relaxed role ID parsing to accept plain digits, quoted digits, or `<@&...>` mention tokens while ignoring invalid entries.

## Environment
- Continue configuring `ADMIN_ROLE_ID` with a single token (digits, quoted digits, or `<@&id>`).
- Continue configuring `STAFF_ROLE_IDS` as comma/space separated tokens (same acceptable formats).
- No new environment keys were introduced.
