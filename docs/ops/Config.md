# Configuration Reference — Phase 3 + 3b

## Live `!config` embed example
```
Configuration Snapshot — prod
Guilds: Clash Champs (Recruitment), Clash Champs Lounge (Onboarding)
Sheets: Recruitment → 1aBCDefGhijKLMnoPqrStuV · Onboarding → 9zYXwvUTsrQpoNMlkJihGFed
Watchers: welcome✅ promo✅
Toggles: STRICT_PROBE=off · ENABLE_NOTIFY_FALLBACK=on · SEARCH_RESULTS_SOFT_CAP=25
Meta: Cache age 42s · Next refresh 02:15 UTC · Actor startup
```

- Guild display names replace raw snowflake IDs across the embed.
- Recruitment and Onboarding Sheet IDs appear in full; click-through URLs remain hidden
  to avoid clutter.
- The meta overlay surfaces cache age, next refresh, and actor pulled from the public
  telemetry snapshot.
- Date/time fields are removed entirely. Embed footers continue to show
  `Bot vX.Y.Z · CoreOps vA.B.C` with no timestamp block.
- No new environment or sheet keys were introduced for Phase 3/3b; reuse the existing
  registry and Config tab structure described below.

> **Note:** Values are pulled live from the runtime cache; embeds no longer carry Discord
> timestamps.

## Environment keys
| Group | Key | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| Core | `DISCORD_TOKEN` | secret | — | Bot token for the Discord application (masked in logs). |
| Core | `ENV_NAME` | string | `dev` | Environment label (`dev`, `test`, `prod`). |
| Core | `GUILD_IDS` | csv | — | Comma-separated guild IDs allowed to load the bot. |
| Core | `TIMEZONE` | string | `UTC` | Olson timezone used for embeds and scheduling. |
| Core | `REFRESH_TIMES` | csv | — | Optional daily refresh windows (HH:MM, comma separated). |
| Sheets | `GSPREAD_CREDENTIALS` | secret | — | Base64-encoded service-account JSON. |
| Sheets | `RECRUITMENT_SHEET_ID` | string | — | Google Sheet ID for recruitment data. |
| Sheets | `ONBOARDING_SHEET_ID` | string | — | Google Sheet ID for onboarding trackers. |
| Roles | `ADMIN_ROLE_IDS` | csv | — | Elevated admin role IDs. |
| Roles | `STAFF_ROLE_IDS` | csv | — | Staff role IDs (welcome + refresh tools). |
| Roles | `RECRUITER_ROLE_IDS` | csv | — | Recruiter role IDs (panels, digests). |
| Roles | `LEAD_ROLE_IDS` | csv | — | Lead role IDs for escalations. |
| Channels | `RECRUITERS_THREAD_ID` | snowflake | — | Thread receiving recruitment updates. |
| Channels | `WELCOME_GENERAL_CHANNEL_ID` | snowflake | — | Public welcome channel ID (optional). |
| Channels | `WELCOME_CHANNEL_ID` | snowflake | — | Private welcome ticket channel ID. |
| Channels | `PROMO_CHANNEL_ID` | snowflake | — | Promo ticket channel ID. |
| Channels | `LOG_CHANNEL_ID` | snowflake | — | Primary log channel ID (#bot-production). |
| Channels | `NOTIFY_CHANNEL_ID` | snowflake | — | Fallback alert channel ID. |
| Channels | `NOTIFY_PING_ROLE_ID` | snowflake | — | Role pinged for urgent alerts. |
| Media | `PUBLIC_BASE_URL` | url | — | External base URL for `/emoji-pad`; falls back to `RENDER_EXTERNAL_URL` when unset. |
| Media | `RENDER_EXTERNAL_URL` | url | — | Render.com external hostname used when `PUBLIC_BASE_URL` is not provided. |
| Media | `EMOJI_MAX_BYTES` | int | `2000000` | Maximum emoji payload size accepted by `/emoji-pad`. |
| Media | `EMOJI_PAD_SIZE` | int | `256` | Square canvas dimension for padded emoji PNGs. |
| Media | `EMOJI_PAD_BOX` | float | `0.85` | Fraction of the canvas filled by the emoji glyph after padding. |
| Media | `TAG_BADGE_PX` | int | `128` | Pixel edge length used when generating clan badge attachments. |
| Media | `TAG_BADGE_BOX` | float | `0.90` | Glyph fill ratio applied during clan badge attachment rendering. |
| Media | `STRICT_EMOJI_PROXY` | bool | `true` | When truthy (`1`), require padded proxy thumbnails instead of raw CDN URLs. |
| Toggles | `WELCOME_ENABLED` | bool | `true` | Enables welcome command plus automation. |
| Toggles | `ENABLE_NOTIFY_FALLBACK` | bool | `true` | Sends alerts to fallback channel when true. |
| Toggles | `STRICT_PROBE` | bool | `false` | Enforces guild allow-list before startup completes. |
| Toggles | `SEARCH_RESULTS_SOFT_CAP` | int | `25` | Soft limit on search results per query. |
| Toggles | _Feature toggles_ | sheet | `FeatureToggles` | Recruitment/placement modules use the `FeatureToggles` worksheet described below. Only `TRUE` enables a feature. |
| Watchdog | `WATCHDOG_CHECK_SEC` | int | `30` | Interval between watchdog polls. |
| Watchdog | `WATCHDOG_STALL_SEC` | int | `45` | Connected stall threshold in seconds. |
| Watchdog | `WATCHDOG_DISCONNECT_GRACE_SEC` | int | `300` | Disconnect grace period before restart. |
| Cache | `CLAN_TAGS_CACHE_TTL_SEC` | int | `900` | TTL for cached clan tags. |
| Cleanup | `CLEANUP_AGE_HOURS` | int | `48` | Age threshold for cleanup jobs. |

### Automation listeners & cron jobs
| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `ENABLE_WELCOME_LISTENERS` | bool | `true` | Event listeners for welcomes. Alias (deprecated): `ENABLE_WELCOME_WATCHER`. |
| `ENABLE_PROMO_LISTENERS` | bool | `true` | Event listeners for promos. Alias (deprecated): `ENABLE_PROMO_WATCHER`. |
| `CRON_REFRESH_CLAN_TAGS` | cron | `15m` | Scheduled clan tag refresh job (logged as `[cron]`). |
| `CRON_REFRESH_SHEETS` | cron | `30m` | Sheets sync cadence (logged as `[cron]`). |
| `CRON_REFRESH_CACHE` | cron | `60m` | Cache warmers and daily roll-up (logged as `[cron]`). |

## Sheet config tabs
Both Google Sheets referenced above must expose a `Config` worksheet with **Key** and
**Value** columns.

### Recruitment sheet keys
- `CLANS_TAB`
- `WELCOME_TEMPLATES_TAB`
- `FEATURE_TOGGLES_TAB`

### Onboarding sheet keys
- `WELCOME_TICKETS_TAB`
- `PROMO_TICKETS_TAB`
- `CLANLIST_TAB`

Leave values blank only if a module is disabled via toggles.

### Feature toggles worksheet

**Config key**

| KEY | VALUE |
| --- | --- |
| `FEATURE_TOGGLES_TAB` | `FeatureToggles` |

**FeatureToggles tab (recruitment Sheet)**

- Headers: `feature_name`, `enabled` (case-insensitive).
- **Only `TRUE` enables a feature.** Any other value (`FALSE`, numbers, text, blank) disables it.
- Seed rows:
  ```
  feature_name,enabled
  member_panel,TRUE
  recruiter_panel,TRUE
  recruitment_welcome,TRUE
  recruitment_reports,TRUE
  placement_target_select,TRUE
  placement_reservations,TRUE
  ```

**Behavior**

- Missing tab or header ⇒ all features disabled; emits one admin-ping warning in the runtime log channel.
- Missing feature row ⇒ that feature disabled; logs one admin-ping warning the first time the key is evaluated.
- Invalid value ⇒ disabled; logs one admin-ping warning per feature key.
- Startup continues regardless; platform services (cache, scheduler, watchdog, RBAC) are never gated.

**Operator flow**

1. Edit the `FeatureToggles` worksheet in the environment’s Mirralith Sheet.
2. Run `!rec refresh config` (or the admin bang alias) to pull the latest worksheet values.
3. Confirm the tab and headers with `!checksheet`; resolve any ⚠️ rows before retrying.

**Troubleshooting**

- Warnings mention the first role listed in `ADMIN_ROLE_IDS` and are posted to the runtime log channel.
- Verify the worksheet name matches the Config key and that headers are spelled correctly.
- Use `!rec refresh config` (or the Ops equivalent) to force the bot to re-read the toggles after a fix.

---

_Doc last updated: 2025-10-22 (v0.9.4 toggles rollout)_
