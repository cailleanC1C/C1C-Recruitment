# Architecture — v0.9.3-phase3b-rc4

## Runtime map
```
Discord Gateway
  ↳ Event handlers (commands, watchers, lifecycle)
      ↳ CoreOps cog & command matrix (tier gated)
      ↳ Watchers (welcome, promo, daily digest)
          ↳ Runtime scheduler (refresh windows, retries)
          ↳ Sheets adapters (recruitment, onboarding)
              ↳ shared.sheets.core (Google API client, cache)
                  ↳ Google Sheets
  ↳ Health server (aiohttp) — /ready, /healthz
```

_Recruitment Search path (Sheets → Matcher) is integrated backend-only and feature-flagged
off in production until the panels ship._

### Legend
- Solid nodes = active in production.
- Dashed nodes = integrated but disabled in production (feature-flagged).
- Grey callouts describe shared helpers used by multiple features.

## Phase 3 dependency highlights
- Boot order: config → runtime → shared Sheets core → recruitment/onboarding adapters →
  features → Discord extensions. Abort boot if config or sheets layers fail.
- Watchdog owns keepalive cadences, stall detection, reconnect timers, and feeds its
  metrics into the health server output.
- Runtime scheduler handles cache refreshes, recruiter digest delivery, and any hygiene
  jobs registered by features.

## Data paths
- Reads: commands and watchers use `sheets.recruitment` / `sheets.onboarding`, which
  delegate to `shared.sheets.core` before hitting Google Sheets caches.
- Writes: onboarding watchers call `sheets.onboarding` helpers with bounded retries and
  per-tab cache invalidation.

## Feature toggles & gating
- `WELCOME_ENABLED` controls the welcome command plus both onboarding watchers.
- `ENABLE_WELCOME_WATCHER` and `ENABLE_PROMO_WATCHER` register their event hooks only when
  true.
- RBAC derives from `shared.coreops_rbac`, mapping `ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`,
  `RECRUITER_ROLE_IDS`, and `LEAD_ROLE_IDS` from configuration.

## Health & observability
- `/healthz` aggregates watchdog state, last refresh timestamps, and cache health.
- Structured logs emit `[refresh]`, `[watcher]`, and `[command]` tags with context for
  quick filtering in Discord.
- Failures fall back to stale caches when safe and always raise a structured log to
  `LOG_CHANNEL_ID`.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
