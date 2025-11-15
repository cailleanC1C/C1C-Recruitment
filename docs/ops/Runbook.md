# Ops Runbook

This runbook consolidates the CoreOps lifecycle, cache controls, and telemetry surfaces
introduced in the Phase 3/3b rollout. Use it during startup verification, routine refresh
workflows, and post-change validation.

Older GitHub Actions deploy runs may display "skipped by same-file supersession" when a newer queued push touches overlapping files; treat this as expected sequencing.

## Keep-Alive / Web Server — Expected Boot Line
On successful bind, startup logs:

```
web server listening • port=<n>
```

If this line is missing:
1. Check for import errors near startup (Render logs). An early failure prevents `Runtime.start()` from reaching `start_webserver()`.
2. Confirm no code imports `get_port` from `shared.config`. The only allowed path is `shared.ports.get_port`.
3. Verify `/health` responds. If not, the aiohttp site did not start.
4. After fix, you should see heartbeat/watchdog lines at the configured cadence (`WATCHDOG_*`).

Troubleshooting tip:
- Run `scripts/ci/check_forbidden_imports.sh` locally to catch the deprecated import.

## Help overview surfaces
- `@Bot help` adapts to the caller but always returns four embeds (Overview, Admin / Operational, Staff, User). Sections collapse when the caller cannot run any commands in that slice unless `SHOW_EMPTY_SECTIONS=1` is set, which swaps in a “Coming soon” placeholder for parity checks.
- Commands are discovered dynamically via `bot.walk_commands()` and filtered through `command.can_run(ctx)` so permission decorators stay authoritative.
- Admin covers the operational commands (including `welcome-refresh` and every `refresh*`/`perm*` control), Staff surfaces recruitment flows, Sheet Tools, and milestones, and User lists recruitment, milestones, and the mention-only entry points (`@Bot help`, `@Bot ping`).
- Bare admin bang aliases follow the runtime `COREOPS_ADMIN_BANG_ALLOWLIST`. Admins see `!command` when the allowlist authorizes a bare alias and a runnable bare command exists; otherwise they see `!ops command`. Staff always see `!ops …`, and members only see user-tier commands plus the mention routes.

## Help diagnostics (temporary)
- Toggle on with `HELP_DIAGNOSTICS=1` to emit a one-shot summary of discovered commands for each help invocation. The payload includes visible vs discovered totals plus a `yes`/`no` decision per command, and it sanitizes user and guild names before posting.
- Messages post to the configured log channel resolved by `resolve_ops_log_channel_id`. If that channel is missing, only admins receive a DM copy; staff and members do not get fallbacks.
- Use `HELP_DIAGNOSTICS_TTL_SEC` (default `60`) to throttle repeat posts per audience + guild so repeated help calls during the window reuse the existing diagnostics.

## Startup preloader
1. **Boot:** Render launches the container and the preloader runs before the CoreOps cog
   registers commands.
2. **Warm-up:** The preloader calls `refresh_now(name, actor="startup")` for every
   registered cache bucket (`clans`, `templates`, `clan_tags`).
3. **Logging:** A single success/failure summary posts to the ops channel once warm-up
 completes. Individual `[refresh] startup` lines include bucket, duration, retries, and
  result.
4. **Action:** If any bucket fails to warm, rerun `!ops refresh all` after the bot is
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

### Permissions sync commands
- **`!perm`** — Entry point for the bot permissions toolkit; points admins at the bot
  subcommands when invoked bare.
- **`!perm bot list`** — Summarises the current allow/deny configuration, including totals
  for each bucket. Supports `--json` to emit a downloadable snapshot.
- **`!perm bot allow`** — Adds channels or categories to the allow list and trims matching
  entries from the deny list.
- **`!perm bot deny`** — Adds channels or categories to the deny list and trims matching
  entries from the allow list.
- **`!perm bot remove`** — Removes channels or categories from the stored allow/deny lists
  without adding new entries.
- **`!perm bot sync`** — Applies the stored allow/deny state to Discord overwrites. Runs
  in dry mode by default; pass `--dry false` to persist changes.

### Welcome template cache
- **Command:** `!welcome-refresh` (Admin only)
- **Purpose:** Reloads the `WelcomeTemplates` cache bucket so the next `!welcome` posts
  reflect sheet edits.
- **When to run:** After onboarding updates the sheet or when the welcome copy looks
  stale. Staff must ask an admin to run it; the command now enforces admin gating.

### Config snapshot (`!cfg`)
- **Audience:** Admin / Bot Ops (requires `administrator` permission)
- **Purpose:** Quickly verify merged config values and confirm which sheet supplied them.
- **Usage:** `!cfg [KEY]` defaults to `ONBOARDING_TAB` when no key is provided; values are echoed read-only.
- **Notes:** Use uppercase keys from the Config tab. The response includes the masked sheet ID tail and merged-key count so you can confirm reload health without exposing secrets.

### Onboarding resume helper (`!onb resume`)
- **Audience:** Recruiters / Staff with `Manage Threads`
- **Purpose:** Restore a recruit’s onboarding panel when the original message is missing or stale.
- **Usage:** `!onb resume @member` must be issued inside the recruit’s onboarding ticket thread.
- **Notes:** The command rejects non-thread channels, surfaces “not found” guidance when no saved session exists, and informs staff when the onboarding controller is offline.

### `!reload --reboot`
- Restarts both the Discord modules and the aiohttp runtime after reloading configuration.
- Flushes cached Sheets connections so the next command run observes fresh credentials and tabs.
- Emits the log line `Runtime rebooted via !reload --reboot` once the restart sequence completes.

## Digest & health telemetry
When operators run `!ops digest` or `!ops health`, the embeds render the following fields
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

1. Run `!ops reload` after updating Sheet tab names or ranges.
2. Trigger `!checksheet`.
3. Review the embed for **Tabs**, **Named ranges**, and **Headers**. Missing entries show
   as ⚠️ with the key that failed validation.
4. Optional: `!checksheet --debug` posts the first few rows from each tab so you can
   confirm recruiters see the expected columns.
5. If any validations fail, double-check Sheet permissions and the Config tab contents
   before escalating.

### Validation (dry-run)
Staff can validate the onboarding sheet without starting a flow:
```
!ops onb:check
```
This command reads the **existing** tab defined by `ONBOARDING_TAB` and reports success or the first blocking error (no fallbacks).

### Daily recruiter summary embed
- The “Summary Open Spots” card now renders as three distinct blocks: General Overview,
  Per Bracket (one line per bracket with totals), and Bracket Details (per-clan rows).
- Two zero-width divider fields containing `﹘﹘﹘` separate the blocks so desktop and
  mobile layouts both show clear visual boundaries.

## Reserving a clan seat (`!reserve`)
- Confirm `FEATURE_RESERVATIONS` is enabled in the FeatureToggles worksheet before using the command.
- Run `!reserve <clan_tag>` inside the recruit’s ticket thread (welcome or promo parent).
- Follow the prompts:
  - Mention the recruit or paste their Discord ID.
  - Provide the reservation end date in `YYYY-MM-DD`.
  - Add a short reason when no effective seats remain (`AF` = 0).
- Reply `yes` at the confirmation step to save; `change` lets you re-enter the recruit or date.
- The bot appends the ledger row in `RESERVATIONS_TAB`, then calls `recompute_clan_availability` to update:
  - `AH` — active reservations
  - `AF` — effective open spots (`max(E - AH, 0)`)
  - `AI` — reservation summary (`"<AH> -> usernames"`)
- A success message posts in the thread with the refreshed `AH` and `AF` values.
- Use the convenience commands below to view or manage the reservation once it exists.

### Reservation management commands
- `!reservations` *(inside the recruit’s ticket thread)* — lists every active reservation for that recruit, including clan tag, expiry, recruiter, and status. If none exist you’ll receive a quick confirmation.
- `!reservations <clan_tag>` — recruiter/admin only. Lists all active reservations for that clan, sorted by expiry and showing the ticket code for each hold.
- `!reserve release` *(inside the recruit’s ticket thread)* — immediately cancels the active reservation, restores the clan’s manual open spot by `+1`, and recomputes availability.
- `!reserve extend <YYYY-MM-DD>` *(inside the recruit’s ticket thread)* — updates the reservation expiry date without touching manual open spots.
- `!reserve release` and `!reserve extend` require the ticket thread context so the bot can infer the recruit and reservation row. Both commands log to the ops channel using the `reservation_release` / `reservation_extend` events.

### Welcome ticket closure sync
- Closing a welcome ticket now triggers the same reservation + availability helpers used by `!reserve`:
  - If the recruit joins their reserved clan, the watcher marks the ledger row `closed_same_clan` and leaves manual open spots untouched.
  - If the recruit moves to a different clan, the watcher marks the reservation `closed_other_clan`, restores the reserved clan’s manual open spots by `+1`, and consumes one seat (`-1`) from the final clan.
  - If no reservation existed, the final clan loses one manual open spot (`-1`).
  - Choosing the pseudo tag `NONE` cancels any reservation and restores the reserved clan’s open spot (`+1`).
- After every adjustment the watcher calls `recompute_clan_availability` so `AF`/`AH`/`AI` stay in sync with the ledger.
 
## Reservation lifecycle (daily jobs)
- **12:00 UTC — Reminder**
  - Finds every `active` reservation where `reserved_until == today`.
  - Posts a reminder in the recruit’s ticket thread, pings Recruiter roles, and includes quick instructions for `!reserve extend <date>` and `!reserve release`.
  - Gives Recruiters a six-hour window to extend or intervene before expiry. Each reminder logs `reservation_reminder` with the ticket, clan, and expiry date.
- **18:00 UTC — Auto-release**
  - Marks `active` reservations with `reserved_until <= today` as `expired` in `RESERVATIONS_TAB`.
  - Calls `recompute_clan_availability` for each affected clan to refresh `AF`, `AH`, and `AI`.
  - Posts an expiry notice in the ticket thread (when it still exists) and a summary line in `RECRUITERS_THREAD_ID`.

Both jobs respect the `FEATURE_RESERVATIONS` toggle in the `Feature_Toggles` worksheet. When the flag is disabled they exit without making any changes.

## Features unexpectedly disabled at startup
- **Checks:** Confirm the `FEATURE_TOGGLES_TAB` value points to `FeatureToggles`, headers
  match (`feature_name`, `enabled`), and each enabled row uses `TRUE` (case-insensitive).
- **Signals:** Startup posts an admin-ping warning in the runtime log channel when the tab,
  headers, or row values are missing or invalid.
- **Remediation:** Fix the Sheet, run `!ops reload` (or the admin bang alias), then
  verify the tab with `!checksheet` before retrying the feature.

Doc last updated: 2025-11-30 (v0.9.7)
