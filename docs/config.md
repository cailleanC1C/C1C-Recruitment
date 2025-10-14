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

