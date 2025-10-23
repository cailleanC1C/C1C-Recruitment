# ADR-0006 — Startup Preloader + `bot_info` Cron

- Date: 2025-10-20

## Context

Cold starts on Render free tier clear the in-memory cache. Phase 3b introduced a startup
preloader and recurring cron to keep the `bot_info` bucket current without manual
intervention.

## Decision

- During startup, run `refresh_now(name, actor="startup")` for each registered cache
  bucket before enabling commands.
- Record structured `[refresh]` logs for every startup bucket, noting duration, retries,
  and result.
- Register a scheduler job that refreshes the `bot_info` bucket every 3 hours using the
  public cache API.
- Route both startup and cron refresh logs to the ops channel for visibility.

## Consequences

- Operators can rely on warm caches immediately after deploys without manual intervention.
- `bot_info` embeds stay current even if no commands are executed for several hours.
- Failed startup warmers become visible in logs, prompting manual `!rec refresh all` if
  needed.

## Status

Accepted — 2025-10-20

Doc last updated: 2025-10-22 (v0.9.5)
