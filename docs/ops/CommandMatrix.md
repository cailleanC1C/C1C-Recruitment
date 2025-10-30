# Command Matrix

Legend: ✅ = active command · 🧩 = shared CoreOps surface (available across tiers)

Each entry supplies the one-line copy that powers the refreshed help index. Use these
short descriptions in the dynamic `@Bot help` layout; detailed blurbs live in
[`commands.md`](commands.md). Treat [`../_meta/COMMAND_METADATA.md`](../_meta/COMMAND_METADATA.md)
as the canonical export — regenerate or copy from that sheet when updating this table so
the help system, matrix, and metadata stay synchronized.

- **Audience map:** The renderer walks `bot.walk_commands()` at runtime and maps commands by `access_tier`/`function_group`. Every reply ships four embeds (Overview, Admin / Operational, Staff, User). Sections without runnable commands collapse automatically unless `SHOW_EMPTY_SECTIONS=1` is set, in which case the header renders with “Coming soon”.
- **Alias policy:** Bare bang aliases for admin commands come from `COREOPS_ADMIN_BANG_ALLOWLIST`. Admins see `!command` when the allowlist authorizes a bare alias and a runnable bare command exists; otherwise they see `!ops command`. Staff always see `!ops …` entries, and members only see user-tier commands plus the mention routes (`@Bot help`, `@Bot ping`).
- **Function groups:** Commands declare `function_group` metadata. Valid values are `operational`, `recruitment`, `milestones`, `reminder`, and `general`. The help renderer filters and groups strictly by this map so cross-tier leakage is impossible.

## Admin — CoreOps & refresh controls
_Module note:_ CoreOps now resides in `packages/c1c-coreops` via `c1c_coreops.*` (command behavior unchanged).

| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!config` | ✅ | Admin embed of the live registry with guild names and sheet linkage. | `!config` |
| `!digest` | ✅ | Post the ops digest with cache age, next run, retries, and actor. | `!digest` |
| `!env` | ✅ | Show masked environment snapshot for quick sanity checks. | `!env` |
| `!health` | ✅ | Inspect cache/watchdog telemetry pulled from the public API. | `!health` |
| `!checksheet` | ✅ | Validate Sheets tabs, named ranges, and headers (`--debug` preview optional). | `!checksheet [--debug]` |
| `!refresh [bucket]` | ✅ | Admin bang alias for single-bucket refresh with the same telemetry. | `!refresh [bucket]` |
| `!refresh all` | ✅ | Bang alias for the full cache sweep (same cooldown as the `!ops` variant). | `!refresh all` |
| `!reload [--reboot]` | ✅ | Admin bang alias for config reload plus optional soft reboot. | `!reload [--reboot]` |
| `!ping` | ✅ | Adds a 🏓 reaction so admins can confirm shard responsiveness. | `!ping` |
| `!perm bot list` | ✅ | Show the current bot allow/deny lists with counts and IDs. | `!perm bot list [--json]` |
| `!perm bot sync` | ✅ | Bulk apply bot role overwrites with audit logging. | `!perm bot sync [--dry] [--threads on|off] [--include voice|stage] [--limit N]` |
| `!report recruiters` | ✅ | Posts Daily Recruiter Update to the configured destination (manual trigger; UTC snapshot also posts automatically). | `!report recruiters` |
| `!welcome-refresh` | ✅ | Reload the `WelcomeTemplates` cache bucket before running `!welcome`. | `!welcome-refresh` |

## Recruiter / Staff — recruitment workflows
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!ops checksheet` | 🧩 | Staff view of Sheets linkage for recruitment/onboarding tabs (`--debug` prints sample rows). | `!ops checksheet [--debug]` |
| `!ops config` | 🧩 | Staff summary of guild routing, sheet IDs, env toggles, and watcher states. | `!ops config` |
| `!ops digest` | ✅ | Post the ops digest with cache age, next run, and retries. | `!ops digest` |
| `!ops refresh clansinfo` | 🧩 | Refresh clan roster data when Sheets updates land. | `!ops refresh clansinfo` |
| `!ops refresh all` | 🧩 | Warm every registered cache bucket and emit a consolidated summary (30 s guild cooldown). | `!ops refresh all` |
| `!ops reload [--reboot]` | 🧩 | Rebuild the config registry; optionally schedule a soft reboot. | `!ops reload [--reboot]` |
| `!clanmatch` | 🧩 | Recruiter match workflow (requires recruiter/staff role). [gated: `recruiter_panel`] | `!clanmatch` |
| `!welcome <clan> [@member] [note]` | ✅ | Post the legacy welcome embed with crest, pings, and general notice routing. [gated: `recruitment_welcome`] | `!welcome <clan> [@member] [note]` |

## User — general members
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `@Bot help [command]` | 🧩 | List accessible commands or expand one with usage and tips. | `@Bot help` / `@Bot help <command>` |
| `@Bot ping` | 🧩 | Quick pong reply to confirm the bot is online. | `@Bot ping` |
| `!clan <tag>` | 🧩 | Public clan card with crest + 💡 reaction flip between profile and entry criteria. [gated: `clan_profile`] | `!clan <tag>` |
| `!clansearch` | 🧩 | Member clan search with legacy filters + pager (edits the panel in place). [gated: `member_panel`] | `!clansearch` |

> Feature toggle note — `recruitment_reports` powers the Daily Recruiter Update (manual + scheduled). `placement_target_select` and `placement_reservations` remain stub modules that only log when enabled.

Doc last updated: 2025-10-31 (v0.9.7)
