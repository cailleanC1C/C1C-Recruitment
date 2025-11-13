# Configuration Reference

This page is the single source of truth for runtime configuration. Update it alongside
[`.env.example`](.env.example) so the template stays in parity with production settings.

## Live `!config` embed example
```
Configuration Snapshot — prod
Guilds: Clash Champs (Recruitment), Clash Champs Lounge (Onboarding)
Sheets: Recruitment → 1aBCDefGhijKLMnoPqrStuV · Onboarding → 9zYXwvUTsrQpoNMlkJihGFed
Watchers: welcome✅ promo✅
Toggles: STRICT_PROBE=off · SEARCH_RESULTS_SOFT_CAP=25
Meta: Cache age 42s · Next refresh 02:15 UTC · Actor startup
```

- Guild display names replace raw snowflake IDs across the embed.
- Recruitment and Onboarding Sheet IDs appear in full; click-through URLs remain hidden to avoid clutter.
- The meta overlay surfaces cache age, next refresh, and actor pulled from the public telemetry snapshot.
- Date/time fields are removed entirely. Embed footers continue to show `Bot vX.Y.Z · CoreOps vA.B.C` with no timestamp block.

## Environment keys

> The keys below are authoritative. `.env.example` mirrors this list; CI enforces parity.

**Required at startup:** `DISCORD_TOKEN`, `GSPREAD_CREDENTIALS`, `RECRUITMENT_SHEET_ID`

**Optional for startup:** `ONBOARDING_SHEET_ID`*, `ENV_NAME`, `BOT_NAME`, `PUBLIC_BASE_URL`, `RENDER_EXTERNAL_URL`, `LOG_CHANNEL_ID`, `WATCHDOG_CHECK_SEC`, `WATCHDOG_STALL_SEC`, `WATCHDOG_DISCONNECT_GRACE_SEC`

All sheet-facing modules now require their dedicated `*_SHEET_ID` variables; 

Missing any **Required** key causes the bot to exit with an error at startup. If `LOG_CHANNEL_ID` is empty, Discord channel logging is disabled and a one-time startup warning is emitted.

\* Leaving `ONBOARDING_SHEET_ID` empty allows the process to boot, but onboarding watchers, cache refreshes, and questionnaire-driven commands either skip their work or emit soft errors.

### Core runtime
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `DISCORD_TOKEN` | secret | — | Bot token for the Discord application (masked in logs). |
| `ENV_NAME` | string | `dev` | Environment label (influences watchdog defaults). |
| `BOT_NAME` | string | `C1C-Recruitment` | Display name surfaced in telemetry. |
| `BOT_VERSION` | string | `dev` | Version string surfaced in embeds and logs. |
| `GUILD_IDS` | csv | — | Comma-separated guild IDs allowed to load the bot. |
| `TIMEZONE` | string | `Europe/Vienna` | Olson timezone used for embeds and scheduling. |
| `REFRESH_TIMES` | csv | `02:00,10:00,18:00` | Optional daily refresh windows (HH:MM, comma separated). |
| `PORT` | int | `10000` | Render injects this automatically; local runs fall back to 10000. |
| `LOG_LEVEL` | string | 'INFO' | Python logging level. |
| `LOG_CHANNEL_ID` | snowflake | — | Required for Discord channel logging. If unset or empty, logging to Discord is disabled and a one-time startup warning is emitted. No implicit defaults. |

### Google Sheets access
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | secret | — | Legacy alias for `GSPREAD_CREDENTIALS`. |
| `RECRUITMENT_SHEET_ID` | string | — | Google Sheet ID for recruitment data. |
| `ONBOARDING_SHEET_ID` | string | — | Google Sheet ID for onboarding trackers. |
| `REMINDER_SHEET_ID` | string | — | Google Sheet ID for reminders (service-specific). |
| `MILESTONES_SHEET_ID` | string | — | Google Sheet ID for Milestones (claims, appreciation, shard & mercy, missions) (service-specific). |
| `RECRUITMENT_CONFIG_TAB` | string | `Config` | Worksheet name containing recruitment config. |
| `ONBOARDING_CONFIG_TAB` | string | `Config` | Worksheet name containing onboarding config. |
| `WORKSHEET_NAME` | string | `bot_info` | Fallback for the `clans_tab` worksheet when sheet config is missing. |
| `GSHEETS_RETRY_ATTEMPTS` | int | `5` | Default retry attempts for Sheets API requests. |
| `GSHEETS_RETRY_BASE` | float | `0.5` | Base delay (seconds) for Sheets exponential backoff. |
| `GSHEETS_RETRY_FACTOR` | float | `2.0` | Multiplier for Sheets exponential backoff. |
| `SHEETS_CACHE_TTL_SEC` | int | `900` | TTL for cached worksheet values. |
| `SHEETS_CONFIG_CACHE_TTL_SEC` | int | matches `SHEETS_CACHE_TTL_SEC` | TTL for cached worksheet metadata; defaults to the value above. |

Async handlers must import Sheets helpers from `shared.sheets.async_facade`; the
sync modules remain available for non-async scripts and cache warmers.

### Role and channel routing
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `ADMIN_ROLE_IDS` | csv | — | Elevated admin role IDs. |
| `STAFF_ROLE_IDS` | csv | — | Staff role IDs (welcome + refresh tools). |
| `RECRUITER_ROLE_IDS` | csv | — | Recruiter role IDs (panels, digests). |
| `LEAD_ROLE_IDS` | csv | — | Lead role IDs for escalations. |
| `ADMIN_IDS` | csv | — | Optional list of Discord user IDs treated as admins. |
| `RECRUITERS_THREAD_ID` | snowflake | — | Thread receiving recruitment updates. |
| `WELCOME_GENERAL_CHANNEL_ID` | snowflake | — | Public welcome channel ID (optional). |
| `WELCOME_CHANNEL_ID` | snowflake | — | Private welcome ticket channel ID. |
| `PROMO_CHANNEL_ID` | snowflake | — | Promo ticket channel ID. |
| `NOTIFY_CHANNEL_ID` | snowflake | — | Fallback alert channel ID. |
| `NOTIFY_PING_ROLE_ID` | snowflake | — | Role pinged for urgent alerts. |
| `PANEL_THREAD_MODE` | enum | `same` | `same` posts panels in the invoking channel; `fixed` routes to a dedicated thread. |
| `PANEL_FIXED_THREAD_ID` | snowflake | — | Thread used when `PANEL_THREAD_MODE=fixed`. |
| `REPORT_RECRUITERS_DEST_ID` | snowflake | — | Channel or thread receiving the Daily Recruiter Update. |

### Runtime flags
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `STRICT_PROBE` | bool | `false` | Enforces guild allow-list before startup completes. |
| `SEARCH_RESULTS_SOFT_CAP` | int | `25` | Soft limit on search results per query. |

> Feature toggles such as `recruitment_reports`, `placement_target_select`, `placement_reservations`, and onboarding watcher flags are sourced from the FeatureToggles worksheet.

### Watchdog, cache, and cleanup
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `WATCHDOG_CHECK_SEC` | int | `360` prod / `60` non-prod | Derived from `ENV_NAME`; controls watchdog heartbeat cadence. |
| `WATCHDOG_STALL_SEC` | int | `keepalive*3+30` | Stall threshold derived from the heartbeat cadence. |
| `WATCHDOG_DISCONNECT_GRACE_SEC` | int | `WATCHDOG_STALL_SEC` | Disconnect grace period; falls back to stall threshold. |
| `KEEPALIVE_INTERVAL_SEC` | int | — | Legacy alias for `WATCHDOG_CHECK_SEC`; logs a warning when used. |
| `CLAN_TAGS_CACHE_TTL_SEC` | int | `3600` | TTL for cached clan tags. |
| `REPORT_DAILY_POST_TIME` | HH:MM | `09:30` | UTC time for the Daily Recruiter Update scheduler. |
| `CLEANUP_AGE_HOURS` | int | `72` | Age threshold for cleanup jobs. |

### Media rendering
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `PUBLIC_BASE_URL` | url | — | External base URL for `/emoji-pad`; falls back silently to `RENDER_EXTERNAL_URL` when unset. |
| `RENDER_EXTERNAL_URL` | url | — | Render.com external hostname used when `PUBLIC_BASE_URL` is not provided. |
| `EMOJI_MAX_BYTES` | int | `2000000` | Maximum emoji payload size accepted by `/emoji-pad`. |
| `EMOJI_PAD_SIZE` | int | `256` | Square canvas dimension for padded emoji PNGs. |
| `EMOJI_PAD_BOX` | float | `0.85` | Fraction of the canvas filled by the emoji glyph after padding. |
| `TAG_BADGE_PX` | int | `128` | Pixel edge length used when generating clan badge attachments. |
| `TAG_BADGE_BOX` | float | `0.90` | Glyph fill ratio applied during clan badge attachment rendering. |
| `STRICT_EMOJI_PROXY` | bool | `true` | When truthy (`1`), require padded proxy thumbnails instead of raw CDN URLs. |

> Local development runner (`scripts/dev_run.sh`) now sources `.env` with `set -a; source ./.env`, preserving quoted and space-containing values verbatim.
>
> The `/emoji-pad` proxy enforces HTTPS-only source URLs. Any HTTP attempt returns `400 invalid source host`.

### Recruitment summary theme
- The welcome summary embed resolves its title icon and colour via `shared.theme` helpers. No new environment keys are required; existing `ICON_*` or `COLOR_*` overrides apply automatically.

## Automation listeners & cron jobs

Event listeners and watcher availability are controlled by FeatureToggles sheet entries rather than ENV variables.

> Cron cadences are fixed in code today; scheduled jobs refresh the `clans`, `templates`, and `clan_tags` cache buckets, post `[cache]` summaries to the ops channel, and emit the Daily Recruiter Update at `REPORT_DAILY_POST_TIME` (UTC). Update the scheduler directly if the defaults change.

## Sheet config tabs
Both Google Sheets referenced above must expose a `Config` worksheet with **Key** and **Value** columns.

### Recruitment sheet keys
- 'CLANS_TAB'
- 'WELCOME_TEMPLATES_TAB'
- 'FEATURE_TOGGLES_TAB'
- 'REPORTS_TAB'
- 'RESERVATIONS_TAB'
- 'FEATURE_RESERVATIONS'

`RESERVATIONS_TAB` defaults to `Reservations` and stores the structured reservation
ledger used to derive availability. `FEATURE_RESERVATIONS` gates reservation-aware
workflows; it defaults to `FALSE` when absent so new environments remain inert
until the sheet configuration is populated.

### Onboarding
- `ONBOARDING_TAB` (string) — Sheet tab name containing the onboarding questions with headers `flow, order, qid, label, type, required, maxlen, validate, help, options, visibility_rules, nav_rules`. Preloaded at startup and refreshed weekly; missing or invalid values surface `missing config key: ONBOARDING_TAB` during refresh.

### Onboarding sheet keys
- 'ONBOARDING_TAB'
- 'WELCOME_TICKETS_TAB'
- 'PROMO_TICKETS_TAB'
- 'CLANLIST_TAB'

Leave values blank only if a module is disabled via toggles.

#### Feature Toggles
Lists the current feature toggles loaded from the FeatureToggles sheet.

Example:

```
Feature Toggles:
  recruiter_panel = ON
  member_panel = ON
  placement_target_select = ON
  placement_reservations = ON
  clan_profile = ON
```

### Feature toggles worksheet

**Config key**

| KEY | VALUE |
| --- | --- |
| 'FEATURE_TOGGLES_TAB' | `FeatureToggles` |

**FeatureToggles tab (recruitment Sheet)**

- Headers: `feature_name`, `enabled` (case-insensitive).
- **Only 'TRUE' (ON) enables a feature.** Any other value ('FALSE', numbers, text, blank) disables it.
- Seed rows:
  ```
  feature_name,enabled
  member_panel,TRUE
  recruiter_panel,TRUE
  recruitment_welcome,TRUE
  recruitment_reports,TRUE
  welcome_dialog,TRUE
  placement_target_select,TRUE
  placement_reservations,TRUE
  WELCOME_ENABLED,TRUE
  ENABLE_WELCOME_HOOK,TRUE
  ENABLE_PROMO_WATCHER,TRUE
  ```

**Behavior**

- Missing tab or header ⇒ all features disabled; emits one admin-ping warning in the runtime log channel.
- Missing feature row ⇒ that feature disabled; logs one admin-ping warning the first time the key is evaluated.
- Invalid value ⇒ disabled; logs one admin-ping warning per feature key.
- Startup continues regardless; platform services (cache, scheduler, watchdog, RBAC) are never gated.
- The `recruitment_reports` row powers the Daily Recruiter Update (scheduler + manual command). The `placement_*` rows still control stub modules that only log load state.

Feature enable/disable is always sourced from the FeatureToggles worksheet; ENV variables must not be used for feature flags.

**Operator flow**

1. Edit the `FeatureToggles` worksheet in the environment’s Mirralith Sheet.
2. Run `!ops reload` (or the admin bang alias) to pull the latest worksheet values and rebuild the registry.
3. Confirm the tab and headers with `!checksheet`; resolve any ⚠️ rows before retrying.

**Troubleshooting**

- Warnings mention the first role listed in `ADMIN_ROLE_IDS` and are posted to the runtime log channel.
- Verify the worksheet name matches the Config key and that headers are spelled correctly.
- Use `!ops reload` (or the Ops equivalent) to force the bot to re-read the toggles after a fix.

> **Template note:** The `.env.example` file in this directory mirrors the tables below. Treat that file as the canonical template for new deployments and update both assets together.

Doc last updated: 2025-11-13 (v0.9.7)
