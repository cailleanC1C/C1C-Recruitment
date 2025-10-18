# ADR-0003 — CoreOps Contract (Command Surface and Guardrails)

- Date: 2025-10-18

## Context

Phase 3b established a shared CoreOps module to deliver a unified operational surface across all bots.

## Decision

- Supported commands:
  - `!help`
  - `!ping`
  - `!config`
  - `!digest`
  - `!health`
  - `!env`
  - `!reload`
  - `!checksheet`
  - `!refresh all`
- Cogs export `async def setup(bot)` only.
- Role-based access control uses decorators from `coreops_rbac.py` (`@ops_only`, `@admin_only`).
- External I/O is fail-soft; calls log once and never block hot paths.
- Outputs use the Achievements-bot embed style.
- No hard-coded identifiers; values are sourced from environment variables or `SheetConfig`.
- Consumers use only the public cache and Sheets APIs (`capabilities()`, `refresh_now()`).
- Optional cooldowns (around 30 seconds) may be applied.
- Absolute timestamps are expressed in UTC.

## Consequences

All bots share the same operational contract, improving consistency and reducing support variance. Feature-specific admin commands within CoreOps were considered but rejected to preserve a common surface.

## Status

Accepted — 2025-10-18
