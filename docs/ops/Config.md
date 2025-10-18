# Configuration Reference — Phase 3b

## Environment keys
| Group | Key | Description |
| --- | --- | --- |
| Core | `DISCORD_TOKEN` | Bot token for the Discord application (masked in logs). |
| Core | `ENV_NAME` | Environment label (`dev`, `test`, `prod`). |
| Core | `GUILD_IDS` | Comma-separated guild IDs allowed to load the bot. |
| Core | `TIMEZONE` | Olson timezone used for embeds and scheduling. |
| Core | `REFRESH_TIMES` | Optional daily refresh windows (HH:MM, comma separated). |
| Sheets | `GSPREAD_CREDENTIALS` | Base64-encoded service-account JSON. |
| Sheets | `RECRUITMENT_SHEET_ID` | Google Sheet ID for recruitment data. |
| Sheets | `ONBOARDING_SHEET_ID` | Google Sheet ID for onboarding trackers. |
| Roles | `ADMIN_ROLE_IDS` | CSV of admin role IDs with elevated access. |
| Roles | `STAFF_ROLE_IDS` | CSV of staff role IDs (welcome + refresh tools). |
| Roles | `RECRUITER_ROLE_IDS` | CSV of recruiter role IDs (panels, digests). |
| Roles | `LEAD_ROLE_IDS` | CSV of lead roles for escalations. |
| Channels | `RECRUITERS_THREAD_ID` | Thread receiving recruitment updates. |
| Channels | `WELCOME_GENERAL_CHANNEL_ID` | Public welcome channel ID (optional). |
| Channels | `WELCOME_CHANNEL_ID` | Private welcome ticket channel ID. |
| Channels | `PROMO_CHANNEL_ID` | Promo ticket channel ID. |
| Channels | `LOG_CHANNEL_ID` | Primary log channel ID (#bot-production). |
| Channels | `NOTIFY_CHANNEL_ID` | Fallback alert channel ID. |
| Channels | `NOTIFY_PING_ROLE_ID` | Role pinged for urgent alerts. |
| Toggles | `WELCOME_ENABLED` | Enables welcome command + watchers. |
| Toggles | `ENABLE_WELCOME_WATCHER` | Enables welcome watcher hooks. |
| Toggles | `ENABLE_PROMO_WATCHER` | Enables promo watcher hooks. |
| Toggles | `ENABLE_NOTIFY_FALLBACK` | Sends alerts to fallback channel when true. |
| Toggles | `STRICT_PROBE` | Enforces guild allow-list before startup completes. |
| Toggles | `SEARCH_RESULTS_SOFT_CAP` | Soft limit on search results per query. |
| Watchdog | `WATCHDOG_CHECK_SEC` | Interval between watchdog polls. |
| Watchdog | `WATCHDOG_STALL_SEC` | Connected stall threshold in seconds. |
| Watchdog | `WATCHDOG_DISCONNECT_GRACE_SEC` | Disconnect grace period before restart. |
| Cache | `CLAN_TAGS_CACHE_TTL_SEC` | TTL for cached clan tags. |
| Cleanup | `CLEANUP_AGE_HOURS` | Age threshold for cleanup jobs. |

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
