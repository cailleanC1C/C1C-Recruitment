# Repository Guardrails Summary

This document consolidates the guardrail expectations enforced by CI.

## Documentation Discipline
- Keep configuration references in sync between source, docs, and `.env` templates.
- Update Ops runbooks when command semantics change.
- Reflect architectural decisions in the ADR index within the same PR.

## Codex PR Formatting Rules
- Provide a concise summary of functional changes and impacted files.
- Include a dedicated testing section enumerating each executed check.
- Use repository-relative file paths in citations and reference IDs for logs.

## Automation Notes
- CI posts dedicated summary comments for every PR check (tests, docs lint, guardrails,
  CoreOps audits, etc.). Each summary is bounded by `<!-- …-summary -->` markers so
  reruns refresh the same comment instead of creating duplicates.
- The legacy **Guardrails Summary** for config/docs parity and Discord token scans
  remains in place; address any listed issues before requesting review.

Doc last updated: 2025-10-26 (v0.9.6)
