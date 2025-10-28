<!-- Keep README user-facing -->
<!-- Dev layout reference: recruitment modules now live in modules/recruitment/, -->
<!-- shared sheet adapters consolidate under shared/sheets/. See docs/Architecture.md. -->
# C1C Recruitment Bot v0.9.6

Welcome to the C1C recruitment helper. The bot keeps clan rosters healthy, helps new
friends find their hall, and makes sure every welcome lands in the right place. It links
simple Discord commands to the shared Sheets that power recruitment, so everyone is
working with the same fresh info.

## Role overview

- **Users** get quick answers about clans and bot status without pinging staff.
- **Staff / Recruiters** guide prospects with richer panels and ready-to-send welcome
  messages.
- **Admins** keep the bot running smoothly and coordinate anything that touches the Ops
  toolkit.

## User commands

- `@Bot help` — lists everything your tier can access with a short tip for each item.
- `@Bot ping` — quick check that the bot is awake; it replies with 🏓 when everything is
  running.
- `!clan <tag>` — posts a clan profile card and easy-to-scan entry notes pulled straight
  from the shared Sheets.
- `!clansearch` — opens the interactive search panel so members can browse clan rosters
  on their own.

## Staff quick actions

Staff can use all user commands plus:

- `!clanmatch` — recruiter panel for matching prospects to clans using the latest roster
  info.
- `!welcome [clan] @mention` — posts the saved welcome embed (crest, ping, notice) with
  room for an optional note to the tagged recruit.

Operational commands (anything in the `!ops` family, refresh buttons, sync helpers, and
similar tools) live in the Ops docs. Start with the [Command Matrix](docs/ops/CommandMatrix.md)
and [Perm Command Quickstart](docs/ops/PermCommandQuickstart.md) to confirm what each
command does before you press go.

## Admin snapshot

Admins keep an eye on the bigger picture: making sure the bot stays online, caches stay
fresh, Sheets stay clean, and permissions match the plan. The full toolkit lives in the
Ops suite—see the [Ops Runbook](docs/ops/Runbook.md), [Troubleshooting guide](docs/ops/Troubleshooting.md),
and [Watchers reference](docs/ops/Watchers.md) for the day-to-day checklists and command
names.

## Documentation quick links

- [Architecture overview](docs/Architecture.md)
- [Developer handbook](docs/README.md)
- [Ops Command Matrix](docs/ops/CommandMatrix.md)
- [Ops Runbook](docs/ops/Runbook.md)
- [Ops Troubleshooting guide](docs/ops/Troubleshooting.md)
- [Watcher tooling reference](docs/ops/Watchers.md)

---

Doc last updated: 2025-10-27 (v0.9.6)
