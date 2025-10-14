# CoreOps Module

CoreOps ships with the recruitment bot and provides the operational commands that
admins and staff rely on during Phase 1.

## Commands
All commands use the recruitment prefix (`!rec`) unless you are using an admin bang
shortcut. Examples:

```text
!rec help
!rec health
!rec env
!rec digest
!rec ping
```

- `!rec help` — Lists available CoreOps commands with the current footer.
- `!rec health` — Shows runtime, watchdog heartbeat, and gateway connection status.
- `!rec env` — Prints a redacted environment/config snapshot (no secrets).
- `!rec digest` — Sends a one-line operational digest for quick checks.
- `!rec ping` — Responds immediately so you can confirm reachability.

## Role-based access control
- **Admin** access is granted by the Discord role IDs in `ADMIN_ROLE_IDS`
  (single or multiple IDs supported).
- **Staff** access is granted by the comma or space separated role IDs in
  `STAFF_ROLE_IDS`.
- The build does not use individual user IDs for gating.

## Admin bang shortcuts
Admins can bypass the `!rec` prefix with direct bang commands:

```text
!health
!env
!digest
!help
!ping
```

These shortcuts require the Admin role and map to the same CoreOps command handlers.
`!ping` is available because it is included in the default `COREOPS_COMMANDS` list for
this release.

## Help footer timezone
The help embed footer displays: `Bot v{BOT_VERSION} • CoreOps v1.0.0 • <time>`. The bot
uses Europe/Vienna time when tzdata is available and falls back to UTC if it is not.

## Troubleshooting
Use this checklist if CoreOps feels unresponsive:
1. Confirm the message used an accepted prefix (`!rec`, `!rec `, `rec`, `rec `, or a
   bot mention).
2. Verify the Admin or Staff role IDs are present on the member in Discord.
3. Ensure the bot has the Members intent enabled so role data is delivered.
4. Check that required environment variables (`ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`,
   watchdog intervals) are set in the deployment environment.
5. Review logs for watchdog notices about stalls or reconnect attempts.
