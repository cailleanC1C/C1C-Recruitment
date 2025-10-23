# ADR-0012 — Adopt c1c_coreops package; deprecate shared/coreops_*

## Status

Accepted

## Date

2025-10-23

## Context

CoreOps helpers lived in `shared/coreops_*` alongside infrastructure modules.
That layout made it difficult to share the cog, RBAC checks, and embed renderers
across bots without dragging the entire `shared` package into new runtimes.
Keeping the code dual-homed between `modules/coreops/` scaffolding and shared
files also risked drift once we begin migrating imports for other bots.

## Decision

Create an internal package at `packages/c1c-coreops/src/c1c_coreops/` and copy
the existing CoreOps modules into it unchanged. Leave the `shared/coreops_*`
files as deprecated re-export shims for one release so current importers keep
working while we stage the follow-up import rewrite.

## Consequences

* Canonical CoreOps symbols now live in a reusable package, making downstream
  migrations and testing easier.
* Shared helpers still expose the old module paths, so callers can migrate at
  their own pace during the deprecation window.
* We must follow up with a PR to update imports to `c1c_coreops.*` and remove
  the shims once callers move over.

Doc last updated: 2025-10-23 (v0.9.5)
