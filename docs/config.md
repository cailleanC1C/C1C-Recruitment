# Configuration Reference (Phase 2)

## ENV keys (final names)
| Key | Type | Example | Notes |
|---|---|---|---|
| DISCORD_TOKEN | secret | ••••1234 | Mask in logs. |
| ENV_NAME | enum | dev/test/prod | Drives allow-list selection. |
| GUILD_IDS | list(ids) | 123,456 | Enforced at startup. |
| TIMEZONE | string | Europe/Vienna | Used by scheduler. |
| REFRESH_TIMES | list(HH:MM) | 02:00,10:00,18:00 | Daily tasks. |
| GSPREAD_CREDENTIALS | secret JSON | ••••abcd | Service account JSON. |
| RECRUITMENT_SHEET_ID | id | 1Abc... | Panels + templates. |
| ONBOARDING_SHEET_ID | id | 1Xyz... | Welcome/Promo logs. |
| ADMIN_ROLE_IDS | list(ids) | 111 | Single or many. |
| STAFF_ROLE_IDS | list(ids) | 222 | Required for !welcome*. |
| RECRUITER_ROLE_IDS | list(ids) | 333 | Panel access. |
| LEAD_ROLE_IDS | list(ids) | 444 | As configured. |
| RECRUITERS_THREAD_ID | id | 555 | Daily updates. |
| WELCOME_GENERAL_CHANNEL_ID | id | 666 | Optional general ping. |
| WELCOME_CHANNEL_ID | id | 777 | Welcome watcher parent. |
| PROMO_CHANNEL_ID | id | 888 | Promo watcher parent. |
| LOG_CHANNEL_ID | id | 999 | #bot-production. |
| NOTIFY_CHANNEL_ID | id | 1010 | Fallback notifications. |
| NOTIFY_PING_ROLE_ID | id | 2020 | Optional ping role. |
| WELCOME_ENABLED | bool | true | Enables welcome module. |
| ENABLE_WELCOME_WATCHER | bool | true | Toggle watcher. |
| ENABLE_PROMO_WATCHER | bool | false | Toggle watcher. |
| ENABLE_NOTIFY_FALLBACK | bool | true | Fallback channel pings. |
| STRICT_PROBE | bool | false | Health probe strictness. |
| SEARCH_RESULTS_SOFT_CAP | int | 25 | Panel results soft cap. |
| WATCHDOG_CHECK_SEC | int | 30 | Loop cadence. |
| WATCHDOG_STALL_SEC | int | 120 | Connected stall threshold. |
| WATCHDOG_DISCONNECT_GRACE_SEC | int | 300 | Disconnected grace. |
| CLAN_TAGS_CACHE_TTL_SEC | int | 3600 | Clan tags cache. |
| CLEANUP_AGE_HOURS | int | 72 | Optional cleanup window. |

## Sheet Config tabs
Each sheet must expose a `Config` tab (Key | Value):
- Recruitment: `CLANS_TAB`, `WELCOME_TEMPLATES_TAB`
- Onboarding: `WELCOME_TICKETS_TAB`, `PROMO_TICKETS_TAB`, `CLANLIST_TAB`

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
