# ADR-0008 — Emoji Pipeline Port

- **Date:** 2025-10-22
- **Status:** Draft

---

## Context
Phase 5 work brings the unified recruitment bot in line with the legacy Matchmaker
experience. The historical bot rendered clan search/profile embeds with padded emoji
thumbnails via a `/emoji-pad` proxy, attachment helpers, and view logic that flipped
between lite/search/profile layouts. The unified codebase previously omitted these image
helpers while back-end caches and filters were restored.

---

## Decision
- Port legacy helpers `emoji_for_tag`, `padded_emoji_url`, and `build_tag_thumbnail` into a
  new `recruitment.emoji_pipeline` module with the same defaults and environment switches
  (`PUBLIC_BASE_URL` / `RENDER_EXTERNAL_URL`, `EMOJI_PAD_*`, `TAG_BADGE_*`,
  `STRICT_EMOJI_PROXY`).
- Move the embed builders used by recruitment surfaces into `recruitment.cards` so all
  future commands share the same formatting.
- Introduce view scaffolding (`MemberSearchPagedView`, `SearchResultFlipView`) that calls
  the card builders and attachment helpers without registering Discord commands yet.
- Expose `/emoji-pad` via the aiohttp runtime so thumbnail URLs behave exactly like the
  legacy deployment, including host allowlisting, byte limits, transparent padding, and
  cache headers.

---

## Consequences
- Recruitment commands can enable thumbnails in future PRs without reinventing the legacy
  pipeline.
- The runtime now serves `/emoji-pad`; environments must expose `PUBLIC_BASE_URL` or rely
  on the Render external URL for strict proxy mode.
- `STRICT_EMOJI_PROXY=1` continues to prevent direct CDN URLs; attachments or the proxy are
  required.
- Docs and config tables now cover the emoji/image knobs so Ops can tune byte limits and
  canvas sizing before the UI ships.

---

## Status

**Draft — awaiting command integration in subsequent Phase 5 PRs.**

Doc last updated: 2025-10-26 (v0.9.6)
