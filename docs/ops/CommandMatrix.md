# Command Matrix

Legend: ✅ = active command · 🧩 = shared CoreOps surface (available across tiers)

Each entry supplies the one-line copy that powers the refreshed help index. Use these
short descriptions in `!help` and tier-specific listings; detailed blurbs live in
[`commands.md`](commands.md).

## Admin — CoreOps & refresh controls
_Module note:_ CoreOps now resides in `packages/c1c-coreops` via `c1c_coreops.*` (commands unchanged).

| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!config` | ✅ | Admin embed of the live registry with guild names and sheet linkage. | `!config` |
| `!digest` | ✅ | Post the admin digest with cache age, next run, retries, and actor. | `!digest` |
| `!env` | ✅ | Show masked environment snapshot for quick sanity checks. | `!env` |
| `!health` | ✅ | Inspect cache/watchdog telemetry straight from the public API. | `!health` |
| `!checksheet` | ✅ | Validate Sheets tabs, named ranges, and headers (debug preview optional). | `!checksheet [--debug]` |
| `!rec refresh [bucket]` | 🧩 | Warm a specific cache bucket with actor, age, and retry logging. | `!rec refresh [bucket]` |
| `!rec refresh all` | 🧩 | Warm every registered cache bucket and emit a consolidated summary. | `!rec refresh all` |
| `!rec reload [--reboot]` | 🧩 | Rebuild the config registry; optionally schedule a soft reboot. | `!rec reload [--reboot]` |
| `!refresh [bucket]` | ✅ | Admin bang alias for single-bucket refresh with the same telemetry. | `!refresh [bucket]` |
| `!reload [--reboot]` | ✅ | Admin bang alias for config reload plus optional soft reboot. | `!reload [--reboot]` |

## Recruiter / Staff — recruitment workflows
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!rec checksheet` | 🧩 | Staff view of Sheets linkage for recruitment/onboarding tabs. | `!rec checksheet [--debug]` |
| `!rec config` | 🧩 | Staff summary of guild routing, sheet IDs, and watcher toggles. | `!rec config` |
| `!rec digest` | ✅ | Post the recruiter digest with cache age, next run, and retries. [gated: `recruitment_reports`] | `!rec digest` |
| `!rec refresh clansinfo` | 🧩 | Refresh clan roster data when Sheets updates land. | `!rec refresh clansinfo` |
| `!clanmatch` | 🧩 | Recruiter match workflow (reserved under toggle). [gated: `recruiter_panel`] | `!clanmatch` |
| `!welcome [clan] @mention` | ✅ | Issue a welcome panel seeded from the cached templates. [gated: `recruitment_welcome`] | `!welcome [clan] @mention` |

## User — general members
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!clan <tag>` | 🧩 | Public clan card with crest + 💡 reaction flip between profile and entry criteria. [gated: `clan_profile`] | `!clan <tag>` |
| `!clansearch` | 🧩 | Member clan search with in-place updates (single results message). [gated: `member_panel`] | `!clansearch` |
| `!rec help [command]` | 🧩 | List accessible commands or expand one with usage and tips. | `!rec help` / `!rec help <command>` |
| `!rec ping` | ✅ | Report bot latency and shard status without hitting the cache. | `!rec ping` |

> Daily recruiter digest watcher — [gated: `recruitment_reports`]

Doc last updated: 2025-10-23 (v0.9.5)
