# Command Matrix

Legend: ✅ = active command · 🧩 = shared CoreOps surface (available across tiers)

Each entry supplies the one-line copy that powers the refreshed help index. Use these
short descriptions in the dynamic `@Bot help` layout; detailed blurbs live in
[`../_meta/COMMAND_METADATA.md`](../_meta/COMMAND_METADATA.md).
Treat that export as the canonical source — regenerate or copy from that sheet when updating this table so
the help system, matrix, and metadata stay synchronized.

- **Audience map:** The renderer walks `bot.walk_commands()` at runtime and maps commands by `access_tier`/`function_group`. Every reply ships four embeds (Overview, Admin / Operational, Staff, User). Sections without runnable commands collapse automatically unless `SHOW_EMPTY_SECTIONS=1` is set, in which case the header renders with “Coming soon”.
- **Alias policy:** Bare bang aliases for admin commands come from `COREOPS_ADMIN_BANG_ALLOWLIST`. Admins see `!command` when the allowlist authorizes a bare alias and a runnable bare command exists; otherwise they see `!ops command`. Staff always see `!ops …` entries, and members only see user-tier commands plus the mention routes (`@Bot help`, `@Bot ping`).
- **Function groups:** Commands declare `function_group` metadata. Valid values are `operational`, `recruitment`, `milestones`, `reminder`, and `general`. The help renderer filters and groups strictly by this map so cross-tier leakage is impossible.

## Admin — CoreOps & refresh controls
_Module note:_ CoreOps now resides in `packages/c1c-coreops` via `c1c_coreops.*` (command behavior unchanged).

| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!config` | ✅ | Admin embed of the live registry with guild names and sheet linkage. | `!config` |
| `!cfg [KEY]` | ✅ | Read-only snapshot of a merged config key with the source sheet tail (defaults to ONBOARDING_TAB). | `!cfg [KEY]` |
| `!digest` | ✅ | Post the ops digest with cache age, next run, retries, and actor. | `!digest` |
| `!env` | ✅ | Show masked environment snapshot for quick sanity checks. | `!env` |
| `!health` | ✅ | Inspect cache/watchdog telemetry pulled from the public API. | `!health` |
| `!checksheet` | ✅ | Validate Sheets tabs, named ranges, and headers (`--debug` preview optional). | `!checksheet [--debug]` |
| `!refresh [bucket]` | ✅ | Admin bang alias for single-bucket refresh with the same telemetry. | `!refresh [bucket]` |
| `!refresh all` | ✅ | Bang alias for the full cache sweep (same cooldown as the `!ops` variant). | `!refresh all` |
| `!reload [--reboot]` | ✅ | Admin bang alias for config reload plus optional soft reboot. | `!reload [--reboot]` |
| `!reload onboarding` | ✅ | Reload onboarding questions and log the active schema hash. | `!reload onboarding` |
| `!ping` | ✅ | Adds a 🏓 reaction so admins can confirm shard responsiveness. | `!ping` |
| `!servermap refresh` | ✅ | Rebuild the pinned `#server-map` message(s) from the current Discord category/channel structure. | `!servermap refresh` |
| `!whoweare` | ✅ | Generate the live "Who We Are" role map from the WhoWeAre sheet with snarky blurbs and current role holders. | `!whoweare` |
| `!perm bot list` | ✅ | Admin-only; show the current bot allow/deny lists with counts, IDs, and optional JSON export. More details: [`PermissionsSync`](../modules/PermissionsSync.md). | `!perm bot list [--json]` |
| `!perm bot allow <targets…>` | ✅ | Admin-only; add channels/categories to the allow list and clear conflicting deny entries. Targets accept channel mentions or quoted category names. More details: [`PermissionsSync`](../modules/PermissionsSync.md). | `!perm bot allow <targets…>` |
| `!perm bot deny <targets…>` | ✅ | Admin-only; add channels/categories to the deny list while removing matching allow entries. Use for surgical blocks. More details: [`PermissionsSync`](../modules/PermissionsSync.md). | `!perm bot deny <targets…>` |
| `!perm bot remove <targets…>` | ✅ | Admin-only; remove channels/categories from both allow and deny lists to reset inheritance. More details: [`PermissionsSync`](../modules/PermissionsSync.md). | `!perm bot remove <targets…>` |
| `!perm bot sync` | ✅ | Admin-only; bulk apply bot role overwrites with CSV audits. Defaults to dry-run, prompts before live writes, and respects manual denies. More details: [`PermissionsSync`](../modules/PermissionsSync.md). | `!perm bot sync [--dry] [--threads on|off] [--include voice|stage] [--limit N]` |
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
| `!reserve <clan>` | ✅ | Reserve one clan seat inside a ticket thread and update availability. [gated: `feature_reservations`] | `!reserve <clan>` |
| `!onb resume @member` | ✅ | Resume an onboarding panel for the mentioned recruit inside the active onboarding thread (Manage Threads required). | `!onb resume @member` |
| `!welcome <clan> [@member] [note]` | ✅ | Post the legacy welcome embed with crest, pings, and general notice routing. [gated: `recruitment_welcome`] | `!welcome <clan> [@member] [note]` |

## User — general members
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `@Bot help [command]` | 🧩 | List accessible commands or expand one with usage and tips. | `@Bot help` / `@Bot help <command>` |
| `@Bot ping` | 🧩 | Quick pong reply to confirm the bot is online. | `@Bot ping` |
| `!clan <tag>` | 🧩 | Public clan card with crest + 💡 reaction flip between profile and entry criteria. [gated: `clan_profile`] | `!clan <tag>` |
| `!clansearch` | 🧩 | Member clan search with legacy filters + pager (edits the panel in place). [gated: `member_panel`] | `!clansearch` |
| `!shards [type]` | ✅ | Opens your shard tracker in a private thread with overview + shard tabs. Shows stash, mercy, last pulls, and base chances; optional type selects the default tab. | `!shards [type]` |
| `!shards set <type> <count>` | ✅ | Force-set your shard stash count (channel restricted to Shards & Mercy). | `!shards set <type> <count>` |

Shard tracker buttons are owner-only, use shard-emoji tab selectors, and keep a common `!help shards` footer explaining mercy behaviour.

> Feature toggle note — `recruitment_reports` powers the Daily Recruiter Update (manual + scheduled). `feature_reservations` gates the `!reserve` command. `placement_target_select` remains a stub module that only logs when enabled. `onboarding_rules_v2` enables the deterministic onboarding rules DSL (visibility + navigation); disable to fall back to the legacy string parser.

Doc last updated: 2025-11-20 (v0.9.7)
