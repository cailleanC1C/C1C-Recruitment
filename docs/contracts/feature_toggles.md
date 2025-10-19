# Feature Toggle Contract

## Overview
Phase 4 feature modules load behind a strict fail-closed toggle service. Runtime reads the
`FeatureToggles` worksheet from the recruitment Sheet and only enables features whose
`enabled` column is explicitly set to `TRUE` (case-insensitive). Anything else—blank,
`FALSE`, numeric values, or stray text—forces the feature off.

## Schema
| Column | Type | Notes |
| --- | --- | --- |
| `feature_name` | string | Case-insensitive key that matches the module declaration (see ADR-0007). |
| `enabled` | string | Only accepts `TRUE` (case-insensitive) to enable. All other values disable the feature. |

Rows may appear in any order. Duplicate keys overwrite previous entries; use one row per
feature for clarity.

## Runtime behavior
- Loaders call `shared.features.is_enabled("<key>")` before registering user-facing
  modules.
- `shared.features.refresh()` pulls the worksheet, caches the result in-memory, and fails
  closed if anything goes wrong (missing Sheet, worksheet, headers, or parse errors).
- Missing worksheet/header or unreadable Sheet ⇒ every feature evaluates `False`.
- Missing feature row ⇒ `is_enabled()` returns `False` for that key.
- Invalid value (anything other than `TRUE`) ⇒ feature disabled; value is treated as
  misconfigured.
- The helper emits a single structured warning per issue (global failures, invalid values,
  or missing rows) and pings @Administrator using the first role ID in
  `ADMIN_ROLE_IDS`. Warnings are sent to the runtime log channel.

## Caching & refresh
- The loader keeps a local snapshot. `shared.features.refresh()` can be called manually
  (for example, via `!rec refresh config`) to re-read the Sheet.
- Cache refresh commands that invalidate Sheets also refresh the toggles.

## Operational guidance
1. Ensure the recruitment Sheet `Config` worksheet exposes a `FEATURE_TOGGLES_TAB` key.
   Leave it blank to use the default worksheet name `FeatureToggles`.
2. Add seed rows for every approved feature:
   ```
   feature_name,enabled
   member_panel,TRUE
   recruiter_panel,TRUE
   recruitment_welcome,TRUE
   recruitment_reports,TRUE
   placement_target_select,TRUE
   placement_reservations,TRUE
   ```
3. To enable a feature, write `TRUE` (case-insensitive) in the `enabled` column.
4. Any other value disables the feature. Use `FALSE` or blank intentionally to keep the
   feature off.
5. After editing, run the config refresh command or wait for the next scheduled refresh.

## Troubleshooting
- **Global warning:** "worksheet missing headers" / "worksheet unavailable" — check the
  `FeatureToggles` tab name and headers. Startup continues but all features stay off until
  fixed.
- **Invalid value warning:** e.g., `member_panel` set to `FALSE` — update the cell to
  `TRUE` (enable) or leave blank to keep it disabled without warning.
- **Missing row warning:** `is_enabled()` was called for an undefined key. Add the row with
  the desired value.
- Alerts are delivered to the runtime log channel and mention the Administrator role.

## Approved keys (Phase 4)
Refer to ADR-0007 for the authoritative list of feature keys and descriptions. Future
features must update this contract and the worksheet before deployment.
