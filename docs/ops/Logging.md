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
✅ Welcome panel — actor=@Recruit • thread=#welcome › ticket-123 • channel=#WELCOME CENTER › welcome • result=posted • details:view=panel; source=phrase
✅ Welcome panel — actor=@Guardian • thread=#welcome › ticket-123 • channel=#WELCOME CENTER › welcome • result=posted • details:view=panel; source=emoji; emoji=🎫
⚠️ Welcome panel — actor=@Member • thread=#welcome › ticket-123 • channel=#WELCOME CENTER › welcome • result=not_eligible • details:view=panel; source=emoji; reason=missing_role_or_owner; emoji=🎫
✅ Welcome panel — actor=@Recruit • thread=#welcome › ticket-123 • channel=#WELCOME CENTER › welcome • result=completed • details:view=preview; questions=16; source=panel
❌ Welcome panel — actor=@Recruit • thread=#welcome › ticket-123 • channel=#WELCOME CENTER › welcome • result=error • details:view=panel; source=panel; reason=panel_send
```

### Onboarding panel lifecycle logs
Neutral lifecycle events (open, start, restart) now use the 📘 icon so the feed is quieter, while ✅ still marks a complete run and ⚠️/❌ remain reserved for odd or error conditions. These logs summarize the state change with human labels and omit raw message/thread IDs.

```
📘 onboarding_panel_open — ticket=W0481-caillean • actor=@Recruit • channel=#WELCOME CENTER › welcome • questions=16
📘 onboarding_panel_restart — ticket=W0481-caillean • actor=@Recruit • channel=#WELCOME CENTER › welcome • questions=16 • schema=v1
✅ onboarding_panel_complete — ticket=W0481-caillean • actor=@Recruit • channel=#WELCOME CENTER › welcome • questions=16 • level_detail=Late Game
```

Only include `reason=` when the emoji is ⚠️ or ❌; keep tickets, actors, and channels readable, and rely on schema short codes (e.g., `v1`) instead of raw hashes. IDs are intentionally hidden—if a one-off investigation needs snowflakes, fall back to the structured console logs.

## Dedupe policy
- Window: fixed at 5 seconds. All dedupe is in-memory and process-local.
- Keys:
  - Refresh summaries: `refresh:{scope}:{snapshot_id}` (snapshot ID optional; falls back to a timestamp bucket hash of the bucket list).
  - Welcome summaries: `welcome:{tag}:{recruit_id}` (recruit ID falls back to `0` when unavailable).
  - Permission sync: `permsync:{guild_id}:{ts_bucket}` where `ts_bucket` is derived from the dedupe window.
- Within the window, only the first event is emitted; later duplicates are ignored to keep the Discord channel readable.

## Configuration knobs
No runtime environment flags affect logging templates. Numeric snowflake IDs stay hidden, and refresh summaries always use the concise inline layout.

## Operational rules
- Do not call Discord `fetch_*` APIs purely for logging; the helpers rely on cached objects and gracefully degrade to `#unknown` placeholders.
- Continue emitting structured logs (JSON/stdout) for auditability—only the human-facing Discord posts use the templates above.
---

Doc last updated: 2025-11-17 (v0.9.7)
