# Configuration Reference — Phase 3b

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

### Onboarding sheet keys
- `WELCOME_TICKETS_TAB`
- `PROMO_TICKETS_TAB`
- `CLANLIST_TAB`

Leave values blank only if a module is disabled via toggles.

---

_Doc last updated: 2025-10-18 (v0.9.3-phase3b-rc4)_
