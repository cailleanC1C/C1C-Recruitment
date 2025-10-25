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
- CI posts a **Guardrails Summary** comment on every PR covering config/docs parity
  drift and Discord token leak scans. Address listed issues before requesting review.

Doc last updated: 2025-10-25 (v0.9.5)
