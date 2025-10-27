# REPORT_GUARDRAILS.md

## Summary
| # | Guardrail | Status |
|---|-----------|--------|
|1|Extension contract|Pass|
|2|No hard-coded IDs/names|Pass|
|3|Public cache/sheets APIs only|Pass|
|4|Fail-soft external I/O|Pass|
|5|Output style parity|Pass|
|6|RBAC + cooldowns|Pass|
|7|UTC timestamps|Pass|
|8|No new env/sheet keys|Pass|

## Evidence Table
| Guardrail | Status | Evidence | Notes |
|-----------|--------|----------|-------|
|1|Pass|`async def setup` is the only exported callable in the cog loader.|No stray globals or legacy entry points.|
|2|Pass|Guild allow-list and sheet IDs pulled from config snapshot/environment; env entries iterate discovered keys rather than literals.|No numeric IDs or tab names embedded in code paths.|
|3|Pass|Cache interactions use `cache_list_buckets`, `cache_get_snapshot`, and `cache_telemetry.refresh_now`; sheets use `aget_worksheet`/`acall_with_backoff`.|No `_cache` or private service access.|
|4|Pass|Reload/digest/checksheet/refresh paths wrap external calls, log via sanitize helpers, and provide user-facing fallback messages instead of propagating exceptions.|Error logs throttled via module-level sets to avoid spam.|
|5|Pass|`!config` and `!refresh` produce embeds with tables/fields; refresh embed includes actor/trigger line and totals.|`!health`/`!digest` similarly rely on embed builders with sanitize fallback.|
|6|Pass|Admin/staff gating applied via `@ops_only`/`@admin_only`; ping remains admin-only at root; refresh-all enforces guild cooldowns.|Help rendering checks command tiers before display.|
|7|Pass|Embeds capture `dt.datetime.now(UTC)` for health, digest, env, and refresh summaries to keep timestamps in UTC.|Snapshot formatting also normalizes to UTC in telemetry layer.|
|8|Pass|Env key discovery pulls from runtime snapshot + env vars using configured hints; sheet metadata keys map to env-configurable names rather than literals.|No new constants introduced for sheet/env keys.|

## Command notes
### @Bot help
* Mention entry renders the overview + tier embeds with sanitized replies and friendly fallbacks when no commands or unknown lookups occur.
* Command discovery suppresses denial spam and verifies tier/permission checks before including entries, matching Phase 3 spec behavior.

### @Bot ping
* Mention entry delegates to the prefix proxy, reporting availability if the base handler is missing.
* Base `!ping` remains admin-only and reacts with 🏓, so the proxy inherits RBAC via the shared decorator.

### !config
* Builds a rich embed summarizing env snapshot, allow-list resolution, sheet IDs, and ops channel status with sanitized output and footer metadata.
* Staff can access via `!rec config` (`@ops_only`), while the legacy alias stays admin-only, satisfying gating expectations.

### !digest
* Aggregates cache telemetry into a digest embed and falls back to a formatted text line if embed construction or send fails; logging throttled through sanitize helpers.
* Staff-tier command exposed under both `!rec` and legacy admin alias, maintaining parity with spec.

### !health
* Produces a health embed combining runtime metrics and cache telemetry, with humanized durations and UTC-aware next refresh text.
* Admin-only via both prefix variants, aligned with RBAC requirements.

### !env
* Generates grouped env/config embeds with masked secrets, resolved IDs, UTC timestamp, and footer notes.
* Limited to admins across both command surfaces.

### !reload
* Handles `--reboot` flag parsing, logs failures once, and reports duration to the caller; errors return sanitized warnings instead of aborting.
* Admin-only for both legacy and `!rec` entry points, respecting guardrail + cooldown expectations (no cooldown required here).

### !checksheet
* Iterates configured sheet targets, inspects tabs with backoff, and composes embeds listing results/warnings; errors logged once per sheet/tab context.
* Staff-only via `@ops_only` on both aliases, matching access contract.

### !refresh all
* Lists buckets via telemetry API, refreshes each with result aggregation, then posts a refresh embed (actor • trigger, table, footer) with text fallback on failure.
* Both admin-facing commands apply guild-only, ops/admin gates, and a 30s guild cooldown to prevent spamming.

## Hot spots
* Consider surfacing a distinct warning when a sheet’s config tab key is absent instead of defaulting to "Config" so misconfigured tabs are easier to spot during guardrail checks.

## Risk scan
* No blocking risks observed—extension contract, config sourcing, embed parity, and RBAC controls all validate cleanly in the current codebase.

Doc last updated: 2025-10-27 (v0.9.x)
