# ADR-0005 — Reload vs Refresh (Soft Reboot Flag)

- Date: 2025-10-20

## Context

Operators requested clearer separation between cache refreshes and configuration reloads.
Phase 3b added a soft reboot flag to `!ops reload` and tightened actor logging so ops can
trace who initiated reloads.

## Decision

- `refresh` commands call `refresh_now(name, actor)` on the cache service and never restart
  the bot.
- `reload` rebuilds the config registry, clears TTL caches, and accepts `--reboot` to
  schedule a graceful restart after reload completes.
- Both command families write structured logs including actor, bucket (for refresh),
  duration, retries, and result.
- Guardrails enforce that `--reboot` is only respected for admin-tier callers.

## Consequences

- Ops can resolve stale cache data without touching config state, and vice versa.
- Reloads leave an explicit audit trail, including the actor who scheduled a soft reboot.
- Runbooks can cite a single table to explain when to use each command.

## Status

Accepted — 2025-10-20

Doc last updated: 2025-10-26 (v0.9.6)
