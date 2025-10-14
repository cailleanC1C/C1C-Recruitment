# Configuration — Phase 2

All environments (dev, test, prod) share the same key names. Provide values in `.env.<env>` files and keep secrets out of git.

## Environment keys

| Group | Key | Description |
| --- | --- | --- |
| Core | `DISCORD_TOKEN` | Bot token for the single Discord application. |
| Core | `ENV_NAME` | Environment label (`dev`, `test`, or `prod`). |
| Core | `GUILD_IDS` | Comma-separated guild IDs permitted to load commands. |
| Core | `TIMEZONE` | Olson timezone used for embeds and logging (e.g. `Europe/Vienna`). |
| Core | `REFRESH_TIMES` | Optional cron-style refresh windows for scheduled pulls. |
| Sheets | `GSPREAD_CREDENTIALS` | Base64-encoded service account JSON. |
| Sheets | `RECRUITMENT_SHEET_ID` | Google Sheet ID for recruitment operations. |
| Sheets | `ONBOARDING_SHEET_ID` | Google Sheet ID for onboarding trackers. |
| Roles | `ADMIN_ROLE_IDS` | CSV of guild role IDs with admin-grade access. |
| Roles | `STAFF_ROLE_IDS` | CSV of staff role IDs for standard operations. |
| Roles | `RECRUITER_ROLE_IDS` | CSV of recruiter role IDs for search panels. |
| Roles | `LEAD_ROLE_IDS` | CSV of lead roles with elevated notifications. |
| Channels | `RECRUITERS_THREAD_ID` | Thread receiving search notifications. |
| Channels | `WELCOME_GENERAL_CHANNEL_ID` | Channel for public welcome posts. |
| Channels | `WELCOME_CHANNEL_ID` | Private welcome ticket channel. |
| Channels | `PROMO_CHANNEL_ID` | Channel receiving promo ticket updates. |
| Channels | `LOG_CHANNEL_ID` | Central log sink (maps to #bot-production). |
| Channels | `NOTIFY_CHANNEL_ID` | Fallback notification channel for errors. |
| Channels | `NOTIFY_PING_ROLE_ID` | Role pinged for critical alerts. |
| Toggles | `WELCOME_ENABLED` | Enables recruitment welcome posting. |
| Toggles | `ENABLE_WELCOME_WATCHER` | Enables onboarding welcome watcher. |
| Toggles | `ENABLE_PROMO_WATCHER` | Enables onboarding promo watcher. |
| Toggles | `ENABLE_NOTIFY_FALLBACK` | Sends alerts to `NOTIFY_CHANNEL_ID` when true. |
| Toggles | `STRICT_PROBE` | Requires allow-listed guilds before starting. |
| Toggles | `SEARCH_RESULTS_SOFT_CAP` | Soft limit on search results per query. |
| Watchdog | `WATCHDOG_CHECK_SEC` | Interval between watchdog polls. |
| Watchdog | `WATCHDOG_STALL_SEC` | Seconds without heartbeat before warning. |
| Watchdog | `WATCHDOG_DISCONNECT_GRACE_SEC` | Grace period before reconnect escalation. |
| Cache | `CLAN_TAGS_CACHE_TTL_SEC` | TTL for cached clan tags. |
| Cleanup | `CLEANUP_AGE_HOURS` | Age threshold for cleanup job. |

> Legacy single-role keys (`ADMIN_ROLE_ID`, etc.) are removed. Always supply the plural list variants above.

## Google Sheet Config tab

Each Sheet referenced above must include a `Config` worksheet with two columns: **Key** and **Value**. The bot reads the following rows during startup:

### Recruitment sheet
- `CLANS_TAB`
- `WELCOME_TEMPLATES_TAB`

### Onboarding sheet
- `WELCOME_TICKETS_TAB`
- `PROMO_TICKETS_TAB`
- `CLANLIST_TAB`

Additional keys are ignored until Phase 3 expansion. Leave values blank only if the module is disabled via toggles.
