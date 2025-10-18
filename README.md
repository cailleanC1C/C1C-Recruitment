<!-- Keep README user-facing -->
# C1C Recruitment Bot v0.9.3-phase3b-rc4
Welcome to the C1C recruitment helper. The bot keeps clan rosters healthy, helps new
friends find a hall, and makes sure every welcome lands in the right place.

## What you can do today
- `!rec help` lists the commands available to you right now.
- `!clan <tag>` shows a quick profile for any clan in the cluster.
- `!welcome` posts the standard welcome note once staff place a recruit.
- Recruitment Search surfaces matches straight from Sheets when staff flag a clan for
  review.

> Recruitment Search: pilot • backend active, panels pending release

## Behind the scenes
- Sheets hold all roster data; the bot refreshes automatically throughout the day.
- Watchers keep ticket threads tidy and log every welcome or promo update.
- Staff have extra panels and refresh controls gated behind recruiter/admin roles.

## Need help?
- Ping the recruitment team in Discord for command walkthroughs.
- Something seems off? Drop a note in #bot-production so staff can check the logs.

## More reading (staff only)
- [Architecture](docs/Architecture.md) — system map and data flows.
- [Development](docs/development.md) — web deploy workflow, style rules, and doc map.
- [Ops suite](docs/ops/Runbook.md) — runbooks, command matrix, config tables, and
  troubleshooting references.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
