# ADR-0003 — CoreOps Command Contract

- Date: 2025-10-20

## Context

Phase 3/3b established a shared CoreOps module to deliver a unified operational surface
across all deployments. The work harmonized help output, cache telemetry, and refresh
controls so staff and admins receive identical behavior regardless of guild or hosting
environment.

## Decision

- CoreOps v1.5 ships the following supported commands: `!help`, `!rec help`, `!rec ping`,
  `!rec config`, `!rec digest`, `!rec health`, `!rec refresh <bucket>`, `!rec refresh all`,
  `!rec reload`, and `!checksheet`.
- Cogs expose only `async def setup(bot)` and register commands through the shared loader.
- RBAC is enforced with decorators from `shared.coreops_rbac`, ensuring tier checks occur
  before cache access.
- Command handlers must call public cache helpers for telemetry and refresh work; private
  service members remain off-limits.
- Embeds standardize on version-only footers (no timestamps) and display telemetry fields
  returned by the public API (age, next, retries, actor).
- Refresh commands log actor, bucket, duration, and retries via the shared telemetry
  wrapper, including admin bang aliases.
- Guild/channel/role identifiers resolve from the config registry instead of hard-coded
  constants.
- Guild-level cooldown defaults to 30 seconds for refresh commands to prevent thrash while
  remaining overridable for tests.

## Consequences

- Operators receive a predictable CoreOps experience across environments.
- Documentation (Command Matrix, Runbook, help copy) can rely on a stable command list and
  telemetry shape.
- Adding new operational commands now requires ADR updates to keep the contract explicit.

## Status

Accepted — 2025-10-20
