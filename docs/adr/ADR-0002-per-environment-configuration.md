# ADR-0002 — Per-Environment Configuration

- Date: 2025-10-18

## Context

Phase 3 removed hard-coded identifiers so deployments can maintain parity between production and test environments while simplifying secret rotation.

## Decision

- Tokens, guild, channel, role, and Sheet identifiers are sourced from environment variables or `SheetConfig`.
- `shared/settings.py` centralizes loading and validation.
- Defaults never assume production values; only safe null fallbacks are permitted.

## Consequences

Deployments become reproducible across environments, and rotating credentials or IDs no longer requires code changes.

## Status

Accepted — 2025-10-18
