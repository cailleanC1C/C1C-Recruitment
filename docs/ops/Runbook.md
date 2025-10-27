# Ops Runbook

This runbook consolidates the CoreOps lifecycle, cache controls, and telemetry surfaces
introduced in the Phase 3/3b rollout. Use it during startup verification, routine refresh
workflows, and post-change validation.

Older GitHub Actions deploy runs may display "skipped by same-file supersession" when a newer queued push touches overlapping files; treat this as expected sequencing.

## Startup preloader
1. **Boot:** Render launches the container and the preloader runs before the CoreOps cog
   registers commands.
2. **Warm-up:** The preloader calls `refresh_now(name, actor="startup")` for every
   registered cache bucket (`clans`, `templates`, `clan_tags`).
3. **Logging:** A single success/failure summary posts to the ops channel once warm-up
 completes. Individual `[refresh] startup` lines include bucket, duration, retries, and
  result.
4. **Action:** If any bucket fails to warm, rerun `!rec refresh all` after the bot is
  online. Escalate to platform on-call if two consecutive startups fail for the same
  bucket.

> **Lifecycle tag:** CoreOps lifecycle notices (startup, reload, manual refresh) emit
> `[watcher|lifecycle]` this release. Update dashboards to accept `[lifecycle]` ahead of
> the next release when the dual tag flips off.

## Interpreting logs
- Runtime logs are JSON. Each entry includes `ts`, `level`, `logger`, `msg`, `trace`,
  `env`, and `bot` plus any contextual extras. Example:

  ```json
  {"ts":"2025-10-26T04:12:32.104Z","level":"INFO","logger":"aiohttp.access","msg":"http_request","trace":"0a6c...","env":"prod","bot":"c1c","path":"/ready","method":"GET","status":200,"ms":4}
  ```
- Filter structured logs with your aggregator using `logger:"aiohttp.access"` for
  request summaries or `trace:<uuid>` to follow a specific request across service logs.
- The runtime echoes the active `trace` in both the JSON payload and the `X-Trace-Id`
  response header for quick copy/paste when correlating downstream telemetry.
- Healthy watchdog messages (heartbeat old but latency healthy) now log at INFO and are
  rate-limited; WARN/ERROR entries remain reserved for actionable states.

## Readiness vs Liveness
- `/ready` now reflects required components (`runtime`, `discord`). It returns
  `{"ok": false}` until Discord connectivity triggers `health.set_component("discord", True)`.
- `/health` returns the watchdog metrics plus a `components` map of `{name: {ok, ts}}`.
  A non-200 indicates either the watchdog stalled or a component flipped `ok=False`.
- `/healthz` remains the simple liveness check (`200` while the process and watchdog are
  healthy).

## Refresh vs reload controls
| Control | What it does | When to use | Logging & guardrails |
| --- | --- | --- | --- |
| `refresh` | Hits the public cache API (`refresh_now`) for the named bucket(s). Fails soft per bucket; stale data is served if refresh fails. | Stale cache data, `n/a` ages after reboot, Sheets edits that need to propagate. | `[refresh] trigger=<actor> bucket=<name> duration=<ms> age=<sec> retries=<n> result=<ok|fail>` |
| `reload` | Rebuilds the config registry, clears TTL caches, and (optionally) schedules a graceful soft reboot when `--reboot` is supplied. | Role/config updates, registry edits, onboarding template changes. | `[ops] reload actor=<member> flags=<...> result=<ok|fail>` plus `[ops] reboot scheduled` when requested. |

Both controls record the invoking actor, even when triggered via admin bang aliases.
Manual refreshes never force a restart; even repeated failures leave the bot online while
logging the error for follow-up.

### Welcome template cache
- **Command:** `!welcome-refresh` (Admin only)
- **Purpose:** Reloads the `WelcomeTemplates` cache bucket so the next `!welcome` posts
  reflect sheet edits.
- **When to run:** After onboarding updates the sheet or when the welcome copy looks
  stale. Staff must ask an admin to run it; the command now enforces admin gating.

### `!reload --reboot`
- Restarts both the Discord modules and the aiohttp runtime after reloading configuration.
- Flushes cached Sheets connections so the next command run observes fresh credentials and tabs.
- Emits the log line `Runtime rebooted via !reload --reboot` once the restart sequence completes.

## Digest & health telemetry
When operators run `!rec digest` or `!rec health`, the embeds render the following fields
from the public telemetry API:

| Field | Meaning | Notes |
| --- | --- | --- |
| `age` | Seconds since the cache snapshot was last refreshed. | Healthy values stay below the configured TTL; `n/a` appears while caches warm. |
| `next` | Scheduled UTC timestamp for the next automatic refresh. | Confirms cron cadence and upcoming refresh window. |
| `retries` | Count of retry attempts during the last refresh cycle. | Any non-zero value warrants a log review for that bucket. |
| `actor` | Who triggered the last refresh (`startup`, `cron`, or a Discord user). | Validates guardrail compliance (public API only). |

## Checksheet validation
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

## Features unexpectedly disabled at startup
- **Checks:** Confirm the `FEATURE_TOGGLES_TAB` value points to `FeatureToggles`, headers
  match (`feature_name`, `enabled`), and each enabled row uses `TRUE` (case-insensitive).
- **Signals:** Startup posts an admin-ping warning in the runtime log channel when the tab,
  headers, or row values are missing or invalid.
- **Remediation:** Fix the Sheet, run `!rec refresh config` (or the admin bang alias), then
  verify the tab with `!checksheet` before retrying the feature.

Doc last updated: 2025-10-27 (v0.9.x)
