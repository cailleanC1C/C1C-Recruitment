# Command Matrix

Legend: ✅ = active command · 🧩 = shared CoreOps surface (available across tiers)

Each entry supplies the one-line copy that powers the refreshed help index. Use these
short descriptions in `!help` and tier-specific listings; detailed blurbs live in
[`commands.md`](commands.md).

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
| `!refresh all` | ✅ | Bang alias for the full cache sweep (same cooldown as the `!rec` variant). | `!refresh all` |
| `!reload [--reboot]` | ✅ | Admin bang alias for config reload plus optional soft reboot. | `!reload [--reboot]` |
| `!ping` | ✅ | Adds a 🏓 reaction so admins can confirm shard responsiveness. | `!ping` |

## Recruiter / Staff — recruitment workflows
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!rec checksheet` | 🧩 | Staff view of Sheets linkage for recruitment/onboarding tabs (`--debug` prints sample rows). | `!rec checksheet [--debug]` |
| `!rec config` | 🧩 | Staff summary of guild routing, sheet IDs, env toggles, and watcher states. | `!rec config` |
| `!rec digest` | ✅ | Post the ops digest with cache age, next run, and retries. | `!rec digest` |
| `!rec refresh clansinfo` | 🧩 | Refresh clan roster data when Sheets updates land. | `!rec refresh clansinfo` |
| `!rec refresh all` | 🧩 | Warm every registered cache bucket and emit a consolidated summary (30 s guild cooldown). | `!rec refresh all` |
| `!rec reload [--reboot]` | 🧩 | Rebuild the config registry; optionally schedule a soft reboot. | `!rec reload [--reboot]` |
| `!clanmatch` | 🧩 | Recruiter match workflow (requires recruiter/staff role). [gated: `recruiter_panel`] | `!clanmatch` |
| `!welcome [clan] @mention` | ✅ | Post a cached welcome template for the chosen clan. [gated: `recruitment_welcome`] | `!welcome [clan] @mention` |
| `!rec ping` | 🧩 | Prefix proxy for the admin ping command (still requires admin access). | `!rec ping` |

## User — general members
| Command | Status | Short text | Usage |
| --- | --- | --- | --- |
| `!rec help [command]` | 🧩 | List accessible commands or expand one with usage and tips. | `!rec help` / `!rec help <command>` |
| `!clan <tag>` | 🧩 | Public clan card with crest + 💡 reaction flip between profile and entry criteria. [gated: `clan_profile`] | `!clan <tag>` |
| `!clansearch` | 🧩 | Member clan search with legacy filters + pager (edits the panel in place). [gated: `member_panel`] | `!clansearch` |

> Feature toggle note — `recruitment_reports`, `placement_target_select`, and `placement_reservations` currently load stub modules that only log when enabled.

Doc last updated: 2025-10-26 (v0.9.6)
