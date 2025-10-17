<!-- Keep README user-facing -->
# C1C Recruitment Bot v0.9.3-phase3b-rc4
A Discord bot for the C1C cluster that streamlines **recruiting, welcoming and onboarding** in one runtime.
Recruiter panels, welcome templates and ticket watchers share a single config, scheduler and watchdog.

## Highlights
- 🧭 **Recruitment panels** — `!clanmatch`, `!clansearch`, `!clan` for filtering and placement.
- 💌 **Welcome system** — templated welcomes loaded from Google Sheets.
- 🧾 **Onboarding watchers** — log welcome & promo thread closures; prompt for missing data.
- ⚙️ **Unified runtime** — single watchdog, scheduler, and health layer (Phase 2 & 3 runtime verified).
- 🔄 **Sheets & CoreOps refresh** — async cache layer with retries, scheduled + manual refresh, and structured logging.
- 🔐 **Per-environment configuration** — strict `GUILD_IDS` allow-list per env.
- 🪶 **Zero-code maintenance** — update Google Sheets tabs; bot picks it up on refresh.

## Commands (at a glance)
- `!rec help` shows user/staff commands tailored to the caller; `!help` is admin-only.
- Recruiter tools (`!clanmatch`, `!clansearch`, `!clan <tag>`, `!welcome`) are tiered via
  the shared decorators.
- Admin shortcuts (`!ping`, `!health`, `!env`, `!rec refresh all`) remain restricted to
  configured admin roles.
- See the [Command System Guide](docs/commands.md) for the full Phase 3 catalog and help
  behavior.

## Admin Ops & Diagnostics
- 🔐 Core operations commands are guild-only (no DMs) and restricted to configured Admin/Staff roles.
- 📘 See the [CoreOps contract](docs/coreops_contract.md) for the full command matrix and examples.

## How it works
Recruiters shortlist clans via panels. When a decision is made, `!welcome` renders the template from the **WelcomeTemplates** tab and posts to the clan’s channel.
Watchers detect thread closures and upsert rows into **WelcomeTickets** / **PromoTickets**, keeping records tidy.

## Troubleshooting
- Command not working? -> ping @administrator
- Panel not popping? -> run !ping to see if bot is up.

## Documentation
- 📐 [architecture.md](docs/architecture.md) — High-level layout & watchdog flow
- 🧑‍💻 [development.md](docs/development.md) — Web-based deployment workflow and tier audits
- 📋 [commands.md](docs/commands.md) — Command tiers, help system, RBAC rules
- ⚙️ [ops.md](docs/ops.md) — Environment configuration & deployment workflow
- 🛡️ [coreops_contract.md](docs/coreops_contract.md) — CoreOps runbook for admins/staff
- 🗞️ [CHANGELOG.md](CHANGELOG.md) — Release highlights and tiering changes
- 📜 [contracts/core_infra.md](docs/contracts/core_infra.md) — API & health contract

---

_Doc last updated: 2025-10-17 (v0.9.3-phase3b-rc4)_
