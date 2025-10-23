# ADR-0010 — `!clan` profile cards ship with crest attachments

## Status

Accepted

## Context

Phase 5 reintroduces the single-clan lookup command. The legacy Matchmaker bot
attached crest emoji directly from Discord CDN URLs, while the Phase 3 bot
temporarily removed the command entirely. The emoji pipeline introduced in ADR-008
now delivers padded PNG attachments (with a strict proxy fallback) so crest
imagery can return without violating the recruiter panel requirement that cards
remain text-only.

## Decision

`!clan <tag>` renders the profile embed through `recruitment.cards.make_embed_for_profile`
and applies a crest thumbnail using the emoji pipeline:

* Attempt to build a padded crest attachment via
  `emoji_pipeline.build_tag_thumbnail(...)`.
* Fall back to the emoji proxy URL when attachments are unavailable.
* Only when `STRICT_EMOJI_PROXY` is disabled do we fall back to the raw CDN URL.

The flip view reuses `SearchResultFlipView` with the default mode set to
`profile` and injects builders for both the profile and entry criteria embeds.
The secondary view (`cards.make_embed_for_row_lite`) clears thumbnail data so the
entry criteria side remains text-only.

## Consequences

* Crest thumbnails return for `!clan` (and future `!clansearch`) without
  affecting the recruiter panel, which continues to ship text-only cards.
* Cached Sheets data plus the tag index keep lookup latency low and avoid any
  DB writes.
* The owner-locked flip view allows future commands to supply custom embed
  builders, enabling richer toggles without duplicating UI code.

Doc last updated: 2025-10-22 (v0.9.5)
