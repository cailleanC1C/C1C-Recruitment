# ADR-0007 — Feature Toggles & Recruitment Module Boundaries

- **Date:** 2025-10-19
- **Status:** Draft

---

## Context
The unified C1C bot now operates on a stable core platform that provides async Sheets
access with caching and telemetry, a runtime scheduler and watchdog, a health server and
RBAC enforcement, plus structured logging and fail-soft I/O. These components are
considered foundational services and not user-facing features.

Phase 4 introduces user-facing recruitment and placement features drawn from the legacy
Matchmaker and WelcomeCrew bots. We need a way to enable or disable these features on a
per-environment basis (test vs prod) without impacting platform stability or cache
registration.

---

## Decision

### 1. Platform vs Feature
The bot distinguishes between platform modules (always on) and feature modules
(toggleable).

- **Platform modules**: `coreops`, `modules.common.runtime`, `shared.sheets`, `scheduler`,
  `cache`, `health`, `rbac`, and logging utilities.
- **Feature modules**: user-facing cogs, commands, and scheduled posts that interact with
  Discord or Sheets.

### 2. Feature Registry
A new `FeatureToggles` worksheet exists in both environment Sheets with the following
schema:

| feature_name | enabled_in_test | enabled_in_prod |
|--------------|-----------------|-----------------|

Values are case-insensitive `TRUE`/`FALSE`, `YES`/`NO`, `1`/`0`. A blank cell means the
feature is enabled.

### 3. Implementation
A new module `modules/common/feature_flags.py` loads and caches the `FeatureToggles` worksheet. It
exposes a helper:

```python
from modules.common.feature_flags import is_enabled

if is_enabled("feature_key"):
    await module.setup(bot)
```

`modules.common.runtime.load_extensions` wraps each recruitment module registration with this
check. If the Sheet or worksheet fails to load, all features default to enabled and a
single warning is logged at startup.

### 4. Approved Feature Modules (Phase 4)

| Key | Description |
|-----|-------------|
| `member_panel` | Member-facing clan browser (`!clansearch`), owner-locked panels. |
| `recruiter_panel` | Recruiter-only clan match tool (`!clanmatch`) with filters and thread routing. |
| `recruitment_welcome` | Template-based welcome messages; staff-tier only. |
| `recruitment_reports` | Daily recruiter digest post (v1 scope only). |
| `placement_target_select` | Recruiter-only clan picker modal, using cached clan tags. |
| `placement_reservations` | Recruiter reservation workflow; explicit duration required; writes reserved entries to `bot_info` (to be refactored later). |

### 5. Default Behavior
If a row is missing or the worksheet is unreachable:

- `is_enabled()` returns `False` (fail closed).
- A single admin-ping warning logs the condition and the module remains offline until
  fixed.
- Startup continues without retries.

### 6. Documentation & Operations

- `docs/ops/Config.md` documents how to flip toggles.
- `README.md#feature-toggles` and `docs/contracts/core_infra.md#sheets--config` summarize the
  schema, cache behavior, and fail-closed handling.
- Each new or changed feature must declare its key in code and update the worksheet prior
  to deployment.

---

## Consequences

- Safe per-environment rollout from test to production.
- Prevents regressions by gating new recruitment modules independently.
- Core services remain unaffected by feature status.
- Disabling a feature suppresses its commands, listeners, and schedulers while cache
  warmers, telemetry, and health endpoints remain active.
- Adds one cached Sheet read per boot.
- Future features (e.g., reservation-expiry sweeper) will declare their own toggle key.

---

## Status

**Draft — pending implementation of `modules/common/feature_flags.py` and loader integration.**

Doc last updated: 2025-10-26 (v0.9.6)
