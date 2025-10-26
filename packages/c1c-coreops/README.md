# c1c-coreops

CoreOps consolidates the administrative cog that powers our recruitment bots
alongside the helper modules it depends on (RBAC, embed renderers, tag helpers,
and bang-command detection). The goal of this package is to give the other C1C
automation projects a single place to pull the “ops surface” without copying the
implementation files.

At the moment this bundle is still **tightly coupled to the monorepo**. Until the
dependencies listed below are extracted or stubbed, treat the distribution as
internal only.

## Package layout

| Module | Responsibility |
| --- | --- |
| `c1c_coreops.cog` | Discord cog that registers the CoreOps command set, wires telemetry, and formats responses using the renderer helpers. |
| `c1c_coreops.config` | Parses environment variables into a normalized `CoreOpsSettings` dataclass and exposes lookup helpers used by the cog. |
| `c1c_coreops.prefix` | Detects `!<command>` bang shortcuts for admin users and maps them back to registered bot commands. |
| `c1c_coreops.rbac` | Role- and permission-based access checks that align with how the recruitment runtime stores allow lists. |
| `c1c_coreops.render` | Embed builders and formatting utilities used by CoreOps telemetry commands. |
| `c1c_coreops.tags` | Emits the lifecycle log tags shared across CoreOps processes. |

Unit tests that exercise aliasing logic and help-surface completeness live under
`packages/c1c-coreops/tests/` and can be executed with `pytest packages/c1c-coreops/tests -q`.

## Runtime dependencies

The cog currently imports several modules that are **not** shipped with this
package:

* `config.runtime` — provides bot identity, prefix, and watchdog settings.
* `modules.common.feature_flags` / `modules.common.runtime` — feature toggle refresh and runtime scheduling helpers.
* `shared.*` packages — supply cache, Sheets, telemetry, and redaction helpers
  relied upon by the command implementations.

Any bot that installs `c1c-coreops` must therefore install it inside the C1C
monorepo or provide compatible shims for the above modules. This is the primary
blocker for distributing the cog to other projects today.

## Shipping readiness

Before we can ship this package to other bots we need to:

1. Publish the shared support modules listed above (or replace them with
   injectable interfaces) so downstream bots are not forced to vendor the entire
   repository.
2. Document the minimum Discord intents and configuration required by the cog so
   new bots can configure permissions safely.
3. Establish a versioning strategy; the current `0.0.0` placeholder should be
   replaced with a semver stream that matches the CoreOps release cadence.

Until these steps are complete, mark the package as experimental if it is added
to another project.

## Local development

1. Install dev dependencies (pytest, discord.py) via the repo’s standard tools.
2. Run the focused test suite with `pytest packages/c1c-coreops/tests -q` to match the
   CI configuration.
3. Update `pyproject.toml` and this README when exposing new public APIs.

Please keep this README up to date whenever dependencies change so other teams
can evaluate the work required to adopt CoreOps.

Doc last updated: 2025-10-26 (v0.9.6)
