# Feature Toggle Contract

## Overview
Phase 4 introduces environment-aware feature toggles for recruitment and placement
modules. Toggles are defined in a shared Google Sheets worksheet named `FeatureToggles`.
The bot treats the worksheet as the source of truth for deciding whether to load
user-facing modules.

## Schema
| Column | Type | Notes |
| --- | --- | --- |
| `feature_name` | string | Unique key that matches the module declaration (see ADR-0007). |
| `enabled_in_test` | tri-state | Accepts `TRUE/FALSE`, `YES/NO`, `1/0` (case-insensitive). Blank → enabled. |
| `enabled_in_prod` | tri-state | Same semantics as `enabled_in_test`. |

Rows may appear in any order. The loader performs a case-insensitive comparison on the
`feature_name` column.

## Runtime behavior
- Module loaders call `shared.features.is_enabled(key)` before registering extensions.
- When the worksheet is reachable, the helper resolves the environment-specific column
  (based on `ENV_NAME`). Any blank or truthy cell yields `True`; explicit falsey cells
  yield `False`.
- If the worksheet or Sheet cannot be loaded, all features default to enabled and the bot
  logs a single startup warning: `FeatureToggles unavailable; assuming enabled`.

## Caching & refresh
- The worksheet is cached using the standard Sheets cache layer.
- Cache invalidation follows the same refresh cadence as other Sheets tabs; a manual
  refresh via the runtime cache commands also clears the toggle cache.
- Operators can toggle features by editing the worksheet and forcing a cache refresh (or
  waiting for the next scheduled refresh).

## Operational guidance
1. Add or update the `feature_name` row in both environment Sheets.
2. Set the environment-specific column to `FALSE`/`NO`/`0` to disable the feature.
3. Leave the cell blank or set it to `TRUE`/`YES`/`1` to enable.
4. Save the Sheet; the bot picks up the change on the next cache refresh.

## Approved keys (Phase 4)
Refer to ADR-0007 for the authoritative list of feature keys and descriptions. Future
features must document their keys in both the ADR and code modules.
