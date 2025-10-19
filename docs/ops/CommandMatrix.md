# Command Matrix — Phase 3 + 3b

Legend: ✅ = active command · 🧩 = shared CoreOps surface (available across tiers)

Each entry captures the copy that should appear in the updated help system. *Short* text
feeds the tier index returned by `!help`. *Detailed* text powers `!help <command>` and the
per-command embeds that the CoreOps cog renders when operators drill down for usage
guidance.

## Admin — CoreOps & refresh controls
| Command | Status | Short text | Detailed text | Usage |
| --- | --- | --- | --- | --- |
| `!help` | ✅ | Admin-only directory of all command tiers. | Lists every tier with short blurbs. Use it before `!help <command>` during triage to confirm visibility. | — |
| `!rec refresh all` | 🧩 | Warm every registered cache bucket and show actor attribution. | Runs the shared refresh pipeline with safe-fail logging (duration, age, retries, result). Recommended after deploy or when digest ages drift. | `!rec refresh all` |
| `!rec refresh [bucket]` | 🧩 | Warm a single cache bucket on demand. | Targets a specific cache (`clansinfo`, `templates`, `bot_info`, etc.) and reports the same telemetry fields as `all`. Safe for repeated runs; failures isolate to the named bucket. | `!rec refresh [bucket]` |
| `!rec reload [flags…]` | 🧩 | Reload runtime config without restarting. | Pulls the latest config registry, clears TTL caches, and logs the triggering actor. Add `--reboot` for a graceful soft restart once reload completes. | `!rec reload [--reboot]` |
| `!checksheet` | ✅ | Validate required Sheets tabs, headers, and ranges. | Cross-checks configured tabs against live Sheets metadata using the public telemetry snapshot. `--debug` emits the preview rows used to hydrate templates. | `!checksheet [--debug]` |
| `!rec config --admin` | 🧩 | Admin view of the live configuration registry. | Shows guild display names, Sheet IDs, and toggle states straight from the runtime cache. Use after reloads to confirm the new registry snapshot. | `!rec config --admin` |

## Recruiter / Staff — recruitment workflows
| Command | Status | Short text | Detailed text | Usage |
| --- | --- | --- | --- | --- |
| `!rec help` | 🧩 | Tier-aware help index for staff and recruiters. | Mirrors the admin index without admin-only entries. Use to direct staff toward refresh, digest, and watcher helpers. | — |
| `!rec digest` | ✅ | Manually post the recruiter digest embed. | Pulls the digest payload from the cache API, showing age, next scheduled run, and retry history in the footer. Logs caller and result for audit trails. | `!rec digest` |
| `!rec health` | 🧩 | Display cache and watcher telemetry. | Uses public telemetry to show cache age, TTL, next refresh, and retry counts. Ideal for verifying auto-refresh behavior before paging ops. | `!rec health` |
| `!rec refresh templates` | 🧩 | Refresh onboarding templates only. | Warms the templates bucket via the cache service and reports duration, retries, and next run. Use after template edits land in Sheets. | `!rec refresh templates` |
| `!rec refresh clansinfo` | 🧩 | Refresh clan roster data. | Forces a single-bucket refresh with clan counts, retry metadata, and cache age. Safe after recruiter sheet updates or clan merges. | `!rec refresh clansinfo` |
| `!rec config` | 🧩 | Staff-visible configuration summary. | Renders guild names, Sheet IDs, active watchers, and toggle states for recruiters. Helps confirm watcher routing after config changes. | `!rec config` |

## User — general members
| Command | Status | Short text | Detailed text | Usage |
| --- | --- | --- | --- | --- |
| `!rec help` | 🧩 | Member help list with user-tier commands. | Shows eligible commands with single-line summaries. Points members toward ping and clan lookup utilities without exposing staff operations. | — |
| `!rec help <command>` | 🧩 | Detailed help for a specific command. | Expands any accessible command with usage, flags, tier warning, and operational tips. Includes a reminder that advanced commands may require staff roles. | `!rec help <command>` |
| `!rec ping` | ✅ | Check bot latency and status. | Simple health check for end users. Returns websocket latency and shard status without any cache calls. | `!rec ping` |
| `!rec clan <tag>` | ✅ | Look up a clan by tag. | Fetches clan data from the cached Sheets snapshot and returns membership, trophies, and recruiter notes. Automatically invalidates stale cache entries when necessary. | `!rec clan <tag>` |

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
