# CoreOps runtime commands

## `!refresh`
- **RBAC:** Admins via `!refresh`; staff/admins via `!rec refresh`.
- **Usage:** `!refresh all` refreshes every registered cache bucket. Each line of the response shows the bucket label, refresh latency, cache age, and next scheduled run in UTC. Buckets that fail are prefixed with `⚠` but do not abort the run.
- **Clans shortcut:** `!refresh clansinfo` / `!rec refresh clansinfo` skips the manual refresh unless the cache is over an hour old and reuses the same telemetry wrapper when a refresh is necessary.
- **Cooldown:** Commands share a 30 second guild-scoped cooldown to prevent thrashing.

## `!reload`
- **RBAC:** Admins via `!reload`; staff/admins via `!rec reload`.
- **Usage:** `!reload` reloads the environment-backed configuration and confirms with a single status line (`config reloaded · <ms> · by <actor>`).
- **Graceful reboot:** Add `--reboot` to trigger a graceful shutdown after the reload (`graceful reboot scheduled · <ms> · by <actor>`). The platform supervisor restarts the bot.
- **Failure handling:** Unknown flags respond with `⚠️` and a short notice. Reload failures log once and reply with a single-line warning.
