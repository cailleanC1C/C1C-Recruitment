# ADR-0005 — Docs and PR Metadata Workflow

- Date: 2025-10-18

## Context

Phase 3b stabilized automation expectations for Codex-generated pull requests and documentation workflows.

## Decision

- Every PR body ends with an exact `[meta] … [/meta]` block.
- No text may follow the closing tag.
- ADRs are logged for every architectural or behavior-scope change.

## Consequences

Automation can reliably parse PR metadata for labeling and milestone assignment, and historical decisions remain traceable.

## Status

Accepted — 2025-10-18
