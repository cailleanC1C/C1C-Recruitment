# Ops Runbook — Phase 3 + 3b

This runbook consolidates the CoreOps lifecycle, cache controls, and telemetry surfaces
introduced in the Phase 3/3b rollout. Use it during startup verification, routine refresh
workflows, and post-change validation.

## Startup & preloader
1. **Deploy** through Render as usual. The container boots the preloader before the cog
   registers commands.
2. **Cache warm-up** happens automatically via `refresh_now(name, actor="startup")` for
   all registered buckets (Sheets, templates, bot_info, digest payloads).
3. **Logging:**
   - `[ops] startup` confirms preloader start and completion.
   - `[refresh] startup` entries show bucket, duration, result, and retry count.
   - Success and failure summaries post to the ops channel automatically.
4. **Action:** If any startup bucket fails, re-run `!rec refresh all` once the bot is
   online. If two consecutive startup attempts fail, escalate to platform on-call.

## Refresh vs reload
| Control | What it does | When to use | Logged fields |
| --- | --- | --- | --- |
| `refresh` | Hits the cache service public API (`refresh_now`) for the named bucket(s). Safe-fail per bucket; never restarts the bot. | Stale cache data, digest showing `n/a`, Sheets edits that need to propagate. | `[refresh] trigger=<actor> bucket=<name> duration=<ms> age=<sec> retries=<n> result=<ok|fail>` |
| `reload` | Rebuilds the config registry, clears TTL caches, and (optionally) schedules a graceful reboot with `--reboot`. | Role/config updates, toggles changed in Sheets, post-migration config validation. | `[ops] reload actor=<member> flags=<...> result=<ok|fail>` plus optional `[ops] reboot scheduled`. |

Both controls now record the invoking actor, even when triggered via admin bang aliases.

## Digest & health telemetry
When operators run `!rec digest` or `!rec health`, the embeds render the following fields
from the public telemetry API. Use them to triage cache behavior before paging core infra.

| Field | Meaning | Notes |
| --- | --- | --- |
| `age` | Seconds since the cache snapshot was last refreshed. | Healthy values stay below the configured TTL; `n/a` appears during warm-up. |
| `next` | Scheduled UTC timestamp for the next automatic refresh. | Derived from scheduler cadence; ensures cron is firing. |
| `retries` | Count of retry attempts during the last refresh cycle. | Non-zero values should trigger log review for the bucket. |
| `actor` | Who triggered the last refresh (startup, cron, manual). | Helps confirm guardrail compliance (no private cache reads). |

## Checksheet workflow
`!checksheet` verifies the link between the configuration registry and the Google Sheets
tabs.

1. Run `!rec reload` after updating Sheet tab names or ranges.
2. Trigger `!checksheet`.
3. Review the embed for **Tabs**, **Named ranges**, and **Headers**. Missing entries show
   as ⚠️ with the key that failed validation.
4. Optional: `!checksheet --debug` posts the first few rows from each tab so you can
   confirm recruiters see the expected columns.
5. If any validations fail, double-check Sheet permissions and the Config tab contents
   before escalating.

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
