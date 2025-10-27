# ADR-0004 — Help System (Short vs Detailed View)

- Date: 2025-10-20

## Context

Phase 3b split the help experience into a short tiered index and detailed per-command
embeds. The change ensures operators can quickly scan available commands and drill into
usage without cluttering the main index.

## Decision

- `@Bot help` renders the overview message: long description plus Admin/Staff/User embeds
  grouped by function (`Config & Health`, `Sheets & Cache`, etc.).
- `@Bot help <command>` renders the detailed embed with usage, tier warnings, and
  operational tips.
- Empty sections collapse unless `SHOW_EMPTY_SECTIONS=true`; every embed footer includes
  version info and the `@Bot help` reminder.
- Detailed embeds always reference the Command Matrix copy to keep documentation and help
  output in sync.

## Consequences

- Admins can validate tier visibility quickly without scrolling through full command
  descriptions.
- Staff and users receive consistent copy across help embeds and documentation.
- Updating command messaging now requires editing the Command Matrix, ensuring a single
  source of truth.

## Status

Accepted — 2025-10-20

Doc last updated: 2025-10-26 (v0.9.6)
