# ADR-0002 — Cache Telemetry Wrapper (Public API only)

- Date: 2025-10-20

## Context

CoreOps embeds rely on cache telemetry to render refresh ages, retry counts, and the last
actor. Phase 3b required a consistent wrapper that exposed this data without reaching into
private cache structures.

## Decision

- Introduce `c1c_coreops.cache_public` as the only import surface for telemetry.
- Expose helper functions such as `get_snapshot(name)`, `get_summary(name)`, and
  `refresh_now(name, actor)` that proxy to the cache service.
- Strip private fields from snapshots before returning them to command handlers.

## Consequences

- CoreOps commands can render consistent embeds while honoring the guardrail against
  touching private cache modules.
- Telemetry consumers (help, digest, health, checksheet) remain stable even if the cache
  service implementation changes.

## Status

Accepted — 2025-10-20

Doc last updated: 2025-10-26 (v0.9.6)
