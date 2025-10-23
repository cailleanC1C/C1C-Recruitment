# ADR-009 — Recruiter panel cards remain text-only

## Status

Draft

## Context

The unified bot is re-enabling the recruiter-facing `!clanmatch` workflow for
Phase 5. The legacy Matchmaker bot rendered crest thumbnails and emoji-rich
cards, which increased payload size and slowed mobile interactions. The
modernized Sheets access layer and embed builders already support recruiter
cards without thumbnail generation.

## Decision

`!clanmatch` in the unified bot ships as a **text-only** panel. The command uses
`recruitment.cards.make_embed_for_row_classic` with thumbnail rendering
explicitly disabled. No emoji padding, crest lookups, or PNG attachments are
loaded as part of the recruiter workflow.

## Consequences

* Recruiters see the classic entry criteria layout without crest imagery,
  matching the legacy text footprint and ensuring fast loads on mobile.
* Other recruitment commands (`!clansearch`, `!clan <tag>`) remain free to add
  crest rendering in follow-up work without affecting recruiter performance.

Doc last updated: 2025-10-22 (v0.9.5)
