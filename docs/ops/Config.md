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
| Toggles | `WELCOME_ENABLED` | bool | `true` | Enables welcome command plus automation. |
| Toggles | `ENABLE_NOTIFY_FALLBACK` | bool | `true` | Sends alerts to fallback channel when true. |
| Toggles | `STRICT_PROBE` | bool | `false` | Enforces guild allow-list before startup completes. |
| Toggles | `SEARCH_RESULTS_SOFT_CAP` | int | `25` | Soft limit on search results per query. |
| Toggles | _Feature toggles_ | sheet | `enabled` | Recruitment/placement modules use the `FeatureToggles` worksheet described below. |
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
- `FeatureToggles`

### Onboarding sheet keys
- `WELCOME_TICKETS_TAB`
- `PROMO_TICKETS_TAB`
- `CLANLIST_TAB`

Leave values blank only if a module is disabled via toggles.

### Feature toggles worksheet
- Worksheet name: `FeatureToggles`
- Columns: `feature_name`, `enabled_in_test`, `enabled_in_prod`
- Accepted values: `TRUE/FALSE`, `YES/NO`, `1/0` (case-insensitive). Leave blank to treat the
  feature as enabled.
- Missing worksheet or lookup failures default to **enabled** for all features. Startup logs a
  single warning: `FeatureToggles unavailable; assuming enabled`.
- Feature keys must match the module declarations listed in ADR-0007.

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
