<!-- Keep README user-facing -->
<!-- Dev layout reference: recruitment modules now live in modules/recruitment/, -->
<!-- shared sheet adapters consolidate under shared/sheets/. See docs/Architecture.md. -->
# C1C Bot - The Woadkeeper v0.9.6

Welcome to the C1C helper. The bot keeps clan rosters healthy, helps new friends find their hall and makes sure every welcome lands in the right place. It links simple Discord commands to the Mirralith Sheets that power recruitment and describe our cluster, so everyone is working with the same fresh info.

## Role overview

- **Users** get quick answers about clans and bot status without pinging staff.
- **Staff** use richer panels with more info to clans needs and ready-to-send welcome messages.
- **Admins** keep the bot running smoothly and coordinate anything that touches the Ops toolkit.

## User commands

- `@<Botname> help` — lists everything you can access with a short tip for each item.
- `@<Botname> ping` — quick check that the bot is awake; it replies with 🏓 when everything is running.
- `!clan <tag>` — posts a clan profile card and entry citeria pulled straight from our Mirraltih.
- `!clansearch` — opens the interactive search panel so members can browse clan rosters on their own.

The bot only shows commands you can actually run; if you need more tools, ask an admin to review your roles.

## Staff quick actions

Staff can use all user commands plus:

- `!clanmatch` — recruiter panel for matching prospects to clans using the latest roster info.
- `!welcome [clan] @mention` — posts a welcome messages with room for an optional note to the tagged recruit in their clans channel and posts a short notice in general chat so they can say hi to the community.

Operational commands (anything that peeks under the hood of the bot like refresh buttons, sync helpers and similar tools) live in the Ops docs. Start with the [Command Matrix](docs/ops/CommandMatrix.md) and [Perm Command Quickstart](docs/ops/PermCommandQuickstart.md) to see what each command does before you press go.

## Admin snapshot

Admins keep an eye on the bigger picture: making sure the bot stays online, caches stay fresh, Sheets stay clean and permissions match the plan. The full toolkit lives in the Ops suite. See the [Ops Runbook](docs/ops/Runbook.md), [Troubleshooting guide](docs/ops/Troubleshooting.md), and [Watchers reference](docs/ops/Watchers.md) for the day-to-day checklists and command names.

## Documentation quick links

- [Architecture overview](docs/Architecture.md)
- [Developer handbook](docs/README.md)
- [Ops Command Matrix](docs/ops/CommandMatrix.md)
- [Ops Runbook](docs/ops/Runbook.md)
- [Ops Troubleshooting guide](docs/ops/Troubleshooting.md)
- [Watcher tooling reference](docs/ops/Watchers.md)

---

Doc last updated: 2025-10-28 (v0.9.6)
