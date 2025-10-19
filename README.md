<!-- Keep README user-facing -->
# C1C Recruitment Bot v0.9.4
Welcome to the C1C recruitment helper. The bot keeps clan rosters healthy, helps new
friends find a hall, and makes sure every welcome lands in the right place.

## What you can do today
- `!rec help` lists the commands available to you right now.
- `!clan <tag>` shows a quick profile for any clan in the cluster.
- `!welcome` posts the standard welcome note once staff place a recruit.
- Recruitment Search surfaces matches straight from Sheets when staff flag a clan for
  review.

> Recruitment Search: pilot • backend active, panels pending release

## Need help?
- Ping the recruitment team in Discord for command walkthroughs.
- Something seems off? Drop a note in #bot-production so staff can check the logs.

## More reading (staff only)
- [Architecture](docs/Architecture.md) — system map and data flows.
- [Development](docs/development.md) — web deploy workflow, style rules, and doc map.
- [Ops suite](docs/ops/Runbook.md) — runbooks, command matrix, config tables, and
  troubleshooting references.

## Emoji pipeline configuration
- `PUBLIC_BASE_URL` — external base for `/emoji-pad` (falls back to `RENDER_EXTERNAL_URL`).
- `RENDER_EXTERNAL_URL` — render.com external hostname when `PUBLIC_BASE_URL` is unset.
- `EMOJI_MAX_BYTES` — maximum emoji payload size in bytes (default: `2000000`).
- `EMOJI_PAD_SIZE` — square canvas size for padded emoji PNGs (default: `256`).
- `EMOJI_PAD_BOX` — fraction of the canvas filled by the emoji glyph (default: `0.85`).
- `TAG_BADGE_PX` — attachment badge size used in search/profile views (default: `128`).
- `TAG_BADGE_BOX` — badge glyph fill ratio for attachments (default: `0.90`).
- `STRICT_EMOJI_PROXY` — when `1`, skip raw CDN thumbnails and require the proxy (default: `1`).

---

_Doc last updated: 2025-10-22 (v0.9.4)_
