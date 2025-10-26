# ADR-0013 — Config & I/O Hardening — Remove prod log fallback, HTTPS-only emoji proxy, non-blocking recruiter Sheets, readiness route

- Date: 2025-10-25

## Context

An audit highlighted four regressions: Discord log posts could silently land in the production channel when non-prod environments omitted `LOG_CHANNEL_ID`; the emoji proxy accepted HTTP sources, allowing downgrade risks; recruiter panel lookups blocked the event loop during cache misses; and the `/ready` endpoint drifted from the published ops contract. Our collaboration contract forbids implicit fallbacks and requires forward-only remediations.

## Decision

- Remove the implicit `LOG_CHANNEL_ID` default. When unset or empty, Discord log posting stays disabled and we emit a single startup warning.
- Enforce HTTPS-only upstreams for the `/emoji-pad` proxy.
- Execute recruiter Sheets reads off the event loop with `asyncio.to_thread` to keep command handlers responsive.
- Restore the `/ready` endpoint alongside `/`, `/health`, and `/healthz`.

## Consequences

- Configuration becomes explicit—staging/test environments cannot leak into production Discord channels by accident.
- Emoji proxy calls ignore HTTP sources, closing downgrade vectors at the edge.
- Recruiter commands stay responsive even during slow Google Sheets calls at the cost of thread hop overhead.
- Ops health checks regain `/ready`, matching dashboards and runbooks.

## Status

Accepted

Doc last updated: 2025-10-26 (v0.9.6)
