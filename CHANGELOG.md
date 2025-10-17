# Changelog

## v0.9.3-phase3b-rc3 — Phase 3b Docs Alignment (2025-10-16)

### CoreOps & Admin Ops
- Admin-only gating standardized across ops commands.
- New `!env` command: grouped, masked output with ID → name resolution.
- Embeds unified: versions in footer, no inline datetime (use message timestamp).
- `!rec refresh all` now posts a single summary embed listing all buckets with duration/result/retries.

## v0.9.3 — Phase 3 Completion (2025-10-16)

### Sheets Access Layer + CoreOps Refresh

### Docs & versioning
– All runtime and docs bumped to v0.9.3.
– Unified runtime confirmed stable across env groups.

### Cache & Async Layer
– Async back-off and retry helpers implemented.
– Safe cancel propagation and non-blocking refresh confirmed.
– TTL defaults: clans 3 h, templates 7 d, clan_tags 7 d.
– Scheduled refresh cadence: 3 h / weekly (Mon 06:00 UTC).
– Background logging to LOG_CHANNEL_ID with actor + trigger tags.

### CoreOps Groundwork
– Refresh commands consolidated into shared CoreOps.
– Admin and Staff roles now use !rec refresh all and !rec refresh clansinfo.
– RBAC guard logic preserved; clear permission errors surfaced.
– Refresher logs record bucket, trigger, actor, duration, result, error.
– `!rec refresh all` now posts a single summary embed listing all buckets with duration/result/retries.

### Diagnostics & Health
– !health embed now displays cache ages, TTLs, and next refresh times (UTC date + time).
– Refresher telemetry captures retry counts and error text across attempts.
– Enhanced observability for manual vs scheduled triggers.
– Embeds standardized: versions moved to footer; inline date/time removed (embed timestamp used).

### Runtime Reliability
– Gspread dependency added to enable template bucket refresh.
– Ops cog removed (merged into CoreOps for clarity).
– Workflow auto-label and milestone fix verified.

## [0.9.3-rc] — Phase 3 rollout (Shared CoreOps refresh)

- CoreOps: unify refresh commands in shared cog; removed duplicate definitions.
- Runtime: add gspread dependency to enable templates bucket refresh.
- Cache: improved refresh failure diagnostics — both first and retry errors are logged.
- Health: 'next' now shows full UTC date + time (YYYY-MM-DD HH:MM UTC).

## [0.9.2] — Phase 2 complete (Per-Environment Configuration)

- README is user-facing and versioned to v0.9.2.
- Stamped v0.9.2 across architecture, development, ops, ops_coreops, contracts.
- Added footer notes: "Doc last updated: 2025-10-15 (v0.9.2)".
- CoreOps: fix refresh subcommand registration; replace private cache calls with public API; relocate staff `!config` summary into CoreOps.
- Sheets access layer migration remains slated for Phase 3; CoreOps expansion for Phase 3b.

## Phase 2 — 2025-11-05

### Added
- Unified single-bot runtime covering recruitment search, welcome, and onboarding watchers.
- Centralized per-environment configuration with shared key set and Config tab requirements.
- Guild allow-list gating at startup and consolidated logging to #bot-production.

### Changed
- CoreOps command surface harmonized to shared `!help`, `!ping`, `!health`, and `!reload` handlers.
- Watchdog defaults aligned across environments with configurable cadence, stall, and grace values.

### Deprecated
- Legacy duplicate environment keys and multi-bot deployment instructions removed from docs.

## v0.1.0 — 2025-10-14

### Added
- CoreOps cog with commands: ping, help, health, env, digest.
- Help embed with footer: "Bot v{BOT_VERSION} • CoreOps v1.0.0 • <Vienna or UTC time>".
- Role-based RBAC: ADMIN_ROLE_IDS (list), STAFF_ROLE_IDS (list). No user-ID gating.
- Admin "bang" shortcuts: !health, !env, !digest, !help (Admin role only).
- Prefix handling: supports !rec, !rec␣, rec, rec␣ and @mention.
- Watchdog mirrored from legacy: keepalive cadence, stall, disconnect grace; connection-aware.
- Socket heartbeat with READY/connect/disconnect tracking and snapshots.
- Health server (/ready, /healthz) bootstrapped for Render.
- GitHub Actions → Render flow: "latest-wins" lane wait/cancel script.

### Changed
- Prefix parsing fix to accept with/without space variants.
- Intents: enabled members intent to support role-aware gating.

### Fixed
- Command registration conflict with discord.py default help (removed default help).
- Help footer timezone fallback (Vienna → UTC if tzdata missing).

## 2025-10-14 — Phase 2: Per-Environment Configuration
- Unified single-bot scaffold with modules imported.
- Centralized env config with `ENV_NAME` and `GUILD_IDS` allow-list.
- One runtime: watchdog, scheduler, health server.
- Logs routed to `LOG_CHANNEL_ID` (#bot-production).
- Final env names standardized; legacy singular admin key deprecated.
- Sheet tab names moved out of env into each Sheet's **Config** tab.
