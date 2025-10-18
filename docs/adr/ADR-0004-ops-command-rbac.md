# ADR-0004 — Ops Command RBAC and Cooldowns

- Date: 2025-10-18

## Context

Operations commands required consistent security guardrails and rate limiting to prevent spam during incident response.

## Decision

- Standardize `@ops_only()` and `@admin_only()` decorators in `coreops_rbac.py`.
- Allow an optional `@cooldown()` decorator to reduce repeated command invocations.
- Source admin role identifiers from environment variables.

## Consequences

Command security is consistent across bots, and audit trails for operational usage are easier to maintain.

## Status

Accepted — 2025-10-18
