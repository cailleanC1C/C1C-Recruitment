<!-- Keep README user-facing -->
# C1C Unified Recruitment Bot v0.9.3
A Discord bot for the C1C cluster that streamlines **recruiting, welcoming, and onboarding** in one runtime.
Recruiter panels, welcome templates, and ticket watchers share a single config, scheduler, and watchdog.

## Highlights
- 🧭 **Recruitment panels** — `!clanmatch`, `!clansearch`, `!clan` for filtering and placement.
- 💌 **Welcome system** — templated welcomes loaded from Google Sheets.
- 🧾 **Onboarding watchers** — log welcome & promo thread closures; prompt for missing data.
- ⚙️ **Unified runtime** — single watchdog, scheduler, and health layer (Phase 2 complete).
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

_Mentions stay outside embeds; embeds carry the visuals._

## Phase status
**Phase 2 complete** — Per-environment configuration and unified runtime/log routing.  
**Phase 3** → Async Sheets layer
**Phase 3b** → CoreOps expansion

## How it works (short)
Recruiters shortlist clans via panels. When a decision is made, `!welcome` renders the template from the **WelcomeTemplates** tab and posts to the clan’s channel.
Watchers detect thread closures and upsert rows into **WelcomeTickets** / **PromoTickets**, keeping records tidy.

## Troubleshooting
- “Command not found” → Check the guild is in the env **GUILD_IDS** allow-list.  
- “Template missing” → Ensure the clan has a row in **WelcomeTemplates**.  
- Sheet edits not reflected? → Wait for the scheduled refresh (02:00 / 10:00 / 18:00) — Phase 3b adds `!reload`.

## Documentation
- 📐 [architecture.md](docs/architecture.md) — High-level layout & watchdog flow  
- 🧑‍💻 [development.md](docs/development.md) — Local setup, prefixes, structure  
- ⚙️ [ops.md](docs/ops.md) — Environment configuration & deployment workflow  
- 🛡️ [ops_coreops.md](docs/ops_coreops.md) — CoreOps runbook for admins/staff  
- 📜 [contracts/core_infra.md](docs/contracts/core_infra.md) — API & health contract

---

_Doc last updated: 2025-10-15 (v0.9.2)_
