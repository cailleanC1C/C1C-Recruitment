# Logging

Humanized logging makes the Discord-facing operational feed readable without losing the structured context that the console logs already provide. All Discord posts now share a single set of helpers, templates, and emoji so the channel reads like a dashboard instead of a firehose of raw IDs.

## Style rules
- Prefer labels over numeric IDs. Helpers automatically resolve guilds, channels, and users from the cache; if an object is missing, a `#unknown`/`unknown guild` placeholder is emitted instead.
- Use concise human units: `fmt_duration` emits seconds, minutes, or hours; `fmt_count` adds thousands separators.
- Hide empty values with `-` and avoid repeating redundant context (e.g., do not repeat the scope when it is part of the emoji/title).
- Emoji prefix the message and communicate status: ✅ success, ⚠️ warning/partial, ❌ error, ♻️ refresh/cache, 🧭 scheduler, 🐶 watchdog, 🔐 permissions, 🛈 neutral.
- Structured logs (JSON/stdout) remain unchanged—only the Discord line format is affected.

## Templates
Each template lives in `shared/logfmt.LogTemplates` and is consumed by the relevant modules. Examples below show the expected output shape.

### Scheduler
```
🧭 **Scheduler** — intervals: clans=3h • templates=7d • clan_tags=7d • next: clans=2025-10-29 00:00 UTC • templates=2025-10-30 00:00 UTC • clan_tags=2025-10-30 00:00 UTC
```

### Allow-list
```
✅ **Guild allow-list** — verified • allowed=[C1C Cluster] • connected=[C1C Cluster]
❌ **Guild allow-list** — violation • connected=[Other Guild] • allowed=[C1C Cluster]
```

### Watchdog
```
🐶 **Watchdog started** — interval=300s • stall=1200s • disconnect_grace=6000s
```

### Refresh
Line mode:
```
♻️ **Refresh** — scope=startup • clan_tags ok (2.7s, 31, ttl) • clans ok (1.0s, 24, ttl) • templates ok (1.3s, 25, ttl) • total=5.8s
```

### Reports
```
✅ **Report: recruiters** — actor=manual • user=Caillean • guild=C1C Cluster • dest=#ops › recruiters-log • date=2025-10-28 • reason=-
```

### Cache
```
♻️ **Cache: clans** — OK • 3.7s
♻️ **Cache: templates** — FAIL • 0.5s • Missing Access (403/50001)
```

### Command errors
```
⚠️ **Command error** — cmd=help • user=Caillean • reason=TypeError: unexpected kwarg `log_failures`
```

### Permission sync
```
🔐 **Permission sync** — applied=57 • errors=0 • threads=on • details: -
🔐 **Permission sync** — applied=0 • errors=57 • threads=on • details: 50× Missing Access (403/50001), 7× Missing Permissions (403/50013)
```

### Welcome
```
✅ **Welcome** — tag=C1CM • recruit=Eir (741852963014785236) • channel=#clans › martyrs-hall (369258147012369258) • result=ok • details: -
⚠️ **Welcome** — tag=C1CM • recruit=Eir (741852963014785236) • channel=#clans › martyrs-hall (369258147012369258) • result=partial • details: general_notice=error (Missing Access)
✅ **Welcome panel** — actor=@Recruit • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=allowed • details: view=welcome_panel; custom_id=welcome.panel.open; message=334455667788990011; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=667788990011223344; target_user_id=667788990011223344; app_perms=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; app_perms_flags=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True
⚠️ **Welcome panel** — actor=@Recruiter • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=denied_role • details: view=welcome_panel; custom_id=welcome.panel.open; message=334455667788990011; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=123456789012345678; app_perms=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; app_perms_flags=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; reason=missing_roles
⚠️ **Welcome panel** — actor=@Member • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=denied_perms • details: view=welcome_panel; custom_id=welcome.panel.open; message=334455667788990011; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=223344556677889900; app_perms=send_messages=True, send_messages_in_threads=False, embed_links=True, read_message_history=True; app_perms_flags=send_messages=True, send_messages_in_threads=False, embed_links=True, read_message_history=True; missing=send_messages_in_threads
⚠️ **Welcome panel** — actor=@Recruiter • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=ambiguous_target • details: view=welcome_panel; custom_id=welcome.panel.open; message=334455667788990011; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=123456789012345678; app_perms=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; app_perms_flags=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; reason=greeting_missing_mention; target_message=445566778899001122
🛈 **Welcome panel** — actor=@Recruiter • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=restarted • details: view=welcome_panel; custom_id=fallback.emoji; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=123456789012345678; app_perms=-; app_perms_flags=-; trigger=phrase_match
❌ **Welcome panel** — actor=@Recruiter • thread=#welcome › ticket-123 (112233445566778899) • parent=#ops › welcome (998877665544332211) • result=error • details: view=welcome_panel; custom_id=welcome.panel.open; message=334455667788990011; thread_id=112233445566778899; parent_id=998877665544332211; actor_id=123456789012345678; app_perms=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; app_perms_flags=send_messages=True, send_messages_in_threads=True, embed_links=True, read_message_history=True; reason=restart_failed
```

## Dedupe policy
- Window: configurable via `LOG_DEDUPE_WINDOW_S` (default 5s). All dedupe is in-memory and process-local.
- Keys:
  - Refresh summaries: `refresh:{scope}:{snapshot_id}` (snapshot ID optional; falls back to a timestamp bucket hash of the bucket list).
  - Welcome summaries: `welcome:{tag}:{recruit_id}` (recruit ID falls back to `0` when unavailable).
  - Permission sync: `permsync:{guild_id}:{ts_bucket}` where `ts_bucket` is derived from the dedupe window.
- Within the window, only the first event is emitted; later duplicates are ignored to keep the Discord channel readable.

## Configuration knobs
- `LOG_DEDUPE_WINDOW_S` (float, default `5`): adjusts the shared dedupe horizon for refresh, welcome, and permission sync events.
- `LOG_REFRESH_RENDER_MODE` (`plain`, `line`, or `table`, default `plain`): toggles between the compact one-line refresh summary and the code-block table layout.
- `LOG_INCLUDE_NUMERIC_IDS` (`true`/`false`, default `true`): appends the raw numeric ID in parentheses after each label when enabled.

## Operational rules
- Do not call Discord `fetch_*` APIs purely for logging; the helpers rely on cached objects and gracefully degrade to `#unknown` placeholders.
- Continue emitting structured logs (JSON/stdout) for auditability—only the human-facing Discord posts use the templates above.
---

Doc last updated: 2025-10-31 (v0.9.7)
