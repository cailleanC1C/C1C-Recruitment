# C1C Unified Recruitment Bot
Single Discord bot with modular capabilities:
- recruitment.search (panels, filters, embeds)
- recruitment.welcome (templated welcome posting)
- onboarding.watcher_welcome (welcome thread close logging)
- onboarding.watcher_promo (promo close logging)

## Phase 2 status
✔ Centralized env config
✔ Guild allow-list by environment
✔ Single runtime (watchdog, scheduler, health server)
✔ Logs routed to #bot-production
✖ Sheets wiring moves to Phase 3
✖ Shared ops commands expansion moves to Phase 3b

## Environment setup
Create `.env.dev`, `.env.test`, `.env.prod` with identical key names and `ENV_NAME=dev|test|prod`.

### Required ENV keys
- Core: `DISCORD_TOKEN`, `ENV_NAME`, `GUILD_IDS`, `TIMEZONE`, `REFRESH_TIMES`
- Sheets: `GSPREAD_CREDENTIALS`, `RECRUITMENT_SHEET_ID`, `ONBOARDING_SHEET_ID`
- Roles: `ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`, `RECRUITER_ROLE_IDS`, `LEAD_ROLE_IDS`
- Channels: `RECRUITERS_THREAD_ID`, `WELCOME_GENERAL_CHANNEL_ID`, `WELCOME_CHANNEL_ID`, `PROMO_CHANNEL_ID`, `LOG_CHANNEL_ID`, `NOTIFY_CHANNEL_ID`, `NOTIFY_PING_ROLE_ID`
- Toggles: `WELCOME_ENABLED`, `ENABLE_WELCOME_WATCHER`, `ENABLE_PROMO_WATCHER`, `ENABLE_NOTIFY_FALLBACK`, `STRICT_PROBE`, `SEARCH_RESULTS_SOFT_CAP`
- Watchdog: `WATCHDOG_CHECK_SEC`, `WATCHDOG_STALL_SEC`, `WATCHDOG_DISCONNECT_GRACE_SEC`
- Cache/Cleanup: `CLAN_TAGS_CACHE_TTL_SEC`, `CLEANUP_AGE_HOURS`

> Note: Legacy singular keys like `ADMIN_ROLE_ID` are deprecated and removed post-Phase 2.

## Sheet Config tabs (required)
Each Google Sheet must have a tab named **Config** with two columns `Key | Value`.
- Recruitment sheet: `CLANS_TAB`, `WELCOME_TEMPLATES_TAB`
- Onboarding sheet: `WELCOME_TICKETS_TAB`, `PROMO_TICKETS_TAB`, `CLANLIST_TAB`

## Logging
All confirmations and errors route to `LOG_CHANNEL_ID` (= #bot-production).

## Run
Deploy with the desired `.env.*`. The bot enforces `GUILD_IDS` allow-list on startup.
