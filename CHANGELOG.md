# Changelog

## [0.9.2] — Phase 2 complete (Per-Environment Configuration)

- README is user-facing and versioned to v0.9.2.
- Stamped v0.9.2 across architecture, development, ops, ops_coreops, contracts.
- Added footer notes: "Doc last updated: 2025-10-15 (v0.9.2)".
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
