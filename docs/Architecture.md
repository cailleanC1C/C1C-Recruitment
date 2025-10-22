# Architecture — v0.9.5

## Runtime map
```
Discord Gateway
  ↳ Event handlers (commands, listeners, lifecycle)
      ↳ CoreOps cog & command matrix (tier gated)
      ↳ Watcher listeners (welcome, promo) [watcher]
          ↳ Runtime scheduler (refresh windows, retries) [cron]
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
- `[watcher]` marks event-driven listeners tied to Discord webhooks.
- `[cron]` marks scheduled jobs emitted by the runtime scheduler.
- Grey callouts describe shared helpers used by multiple features.

## Phase 3 dependency highlights
- Boot order: config → runtime → shared Sheets core → recruitment/onboarding adapters →
  features → Discord extensions. Abort boot if config or sheets layers fail.
- Watchdog owns keepalive cadences, stall detection, reconnect timers, and feeds its
  metrics into the health server output.
- Runtime scheduler handles cron refreshes, recruiter digest delivery, and any hygiene
  jobs registered by feature modules.

## Data paths
- Reads: commands and watcher listeners use `shared.sheets.recruitment` /
  `shared.sheets.onboarding`, which delegate to `shared.sheets.core` before
  hitting Google Sheets caches.
- Writes: onboarding listeners call `shared.sheets.onboarding` helpers with bounded retries and
  per-tab cache invalidation.

## Recruitment visuals pipeline
- `modules.recruitment.cards` & `modules.recruitment.views` compose embeds for clan panels.
- `modules.recruitment.views.recruiter_panel` binds `!clanmatch` to those cards while staying
  text-only (no `emoji_pipeline` dependency).
- `modules.recruitment.emoji_pipeline` resolves guild emoji, falls back when proxies are strict,
  and builds attachment thumbnails when needed.
- `/emoji-pad` (aiohttp) trims, pads, and caches PNG emoji when `PUBLIC_BASE_URL` or
  `RENDER_EXTERNAL_URL` is configured.
- Sheets cache paths remain unchanged; data still flows through `sheets.recruitment`.

## Feature toggles & gating
- `modules.common.feature_flags.is_enabled(<key>)` runs during module boot; missing worksheets,
  or values fail closed and keep the feature offline.
- Backbone services (cache, scheduler, health server, RBAC) never consult the toggle
  sheet and always load.
- Approved keys:
  - `member_panel` — member search panels.
  - `recruiter_panel` — recruiter dashboards and match tools.
  - `recruitment_welcome` — welcome command plus onboarding listeners.
  - `recruitment_reports` — daily recruiter digest watcher and manual digest command.
  - `placement_target_select` — placement picker UI inside panels.
  - `placement_reservations` — reservation workflow for recruiter holds.
- Toggles live in the recruitment Sheet `FeatureToggles` worksheet; `TRUE`/`true`/`1`
  enable a feature, `FALSE`/`false`/`0` disable it. Misconfigurations post a single admin-ping warning to the runtime log
  channel.
- `ENABLE_WELCOME_LISTENERS` and `ENABLE_PROMO_LISTENERS` environment flags still control
  watcher registration independently of the feature sheet.
- RBAC derives from `shared.coreops_rbac`, mapping `ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`,
  `RECRUITER_ROLE_IDS`, and `LEAD_ROLE_IDS` from configuration.

## Health & observability
- `/healthz` aggregates watchdog state, last refresh timestamps, and cache health.
- Structured logs emit `[ops]`, `[cron]`, `[watcher]`, `[refresh]`, and `[command]` tags
  with context for quick filtering in Discord.
- Failures fall back to stale caches when safe and always raise a structured log to
  `LOG_CHANNEL_ID`.

---

_Doc last updated: 2025-10-22 (v0.9.5)_
