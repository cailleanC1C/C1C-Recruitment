<!-- Keep README user-facing -->
# C1C Recruitment Bot v0.9.3
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
| Command | Scope | Purpose |
| --- | --- | --- |
| `!clanmatch` | Recruiter | Opens recruiter panel with filters and paging. |
| `!clansearch` | Public | Member-facing panel with the same filters. |
| `!clan <clantag>` | Any | Quick clan profile card. |
| `!welcome` | Staff/Admin | Posts templated welcome for a placement. |
| `!ping`, `!health`, `!help`, `!digest` | Admin | Liveness, latency, help, daily digest. |

## Admin Ops & Diagnostics
- 🔐 Core operations commands are guild-only (no DMs) and restricted to configured Admin/Staff roles.
- 📘 See the [CoreOps runbook](docs/ops_coreops.md) for the full command matrix and examples.

## How it works
Recruiters shortlist clans via panels. When a decision is made, `!welcome` renders the template from the **WelcomeTemplates** tab and posts to the clan’s channel.
Watchers detect thread closures and upsert rows into **WelcomeTickets** / **PromoTickets**, keeping records tidy.

## Troubleshooting
- Command not working? -> ping @administrator
- Panel not popping? -> run !ping to see if bot is up.

## Documentation
- 📐 [architecture.md](docs/architecture.md) — High-level layout & watchdog flow  
- 🧑‍💻 [development.md](docs/development.md) — Local setup, prefixes, structure  
- ⚙️ [ops.md](docs/ops.md) — Environment configuration & deployment workflow  
- 🛡️ [ops_coreops.md](docs/ops_coreops.md) — CoreOps runbook for admins/staff  
- 📜 [contracts/core_infra.md](docs/contracts/core_infra.md) — API & health contract

---

_Doc last updated: 2025-10-16 (v0.9.3-phase3b-rc3)_
