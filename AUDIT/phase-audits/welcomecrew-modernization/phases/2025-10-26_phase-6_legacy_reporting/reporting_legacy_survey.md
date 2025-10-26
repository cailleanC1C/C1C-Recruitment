# Legacy Reporting Survey – Clanmatch & WelcomeCrew

## 1) Executive Summary
Matchmaker's legacy bot (`bot_clanmatch_prefix.py`) already ships a daily recruiter summary loop, cache warmers, and manual health tooling that feel production-tested but remain tightly bound to sheet layouts and environment flags. The reporting stack leans on gspread pulls with a long-lived cache, prebuilt embed formatters, and structured cleanup loops; observability is console-driven with minimal Discord fallbacks for failures.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L123-L149】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L699-L720】

WelcomeCrew's mono-file bot (`bot_welcomecrew.py`) centralizes operational reporting around backfill runs, sheet connectivity, and watcher status. It couples manual commands with scheduled refreshers and channel pings, exposing rich toggle surfaces but also inheriting sheet-shape assumptions and silent-fail branches that would need modernization before Phase 6 automation.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1188】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1565-L1615】

## 2) Inventory
### Matchmaker (MM) – `bot_clanmatch_prefix.py`
| Path | Type | Entry points | Dependencies | Output shape | Notes |
| --- | --- | --- | --- | --- | --- |
| `.../MM/bot_clanmatch_prefix.py::get_rows` | datasource | `get_rows(force=False)` | gspread client via `GSPREAD_CREDENTIALS`, `GOOGLE_SHEET_ID`, `WORKSHEET_NAME`; TTL `SHEETS_CACHE_TTL_SEC` | List[List[str]] sheet snapshot | 8h cache, clears on `clear_cache`; assumes credentials env is valid, prints boot warnings when missing.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L91-L149】 |
| `.../MM/bot_clanmatch_prefix.py::read_recruiter_summary` | datasource | `read_recruiter_summary()` | Relies on `get_rows`, `_locate_summary_headers` heuristics | Dict[str, Tuple[int,int,int]] keyed by bracket | Fallbacks to screenshot-based column indices; tolerant of missing rows, returns zeros if parse fails.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L566-L591】 |
| `.../MM/bot_clanmatch_prefix.py::build_recruiters_summary_embed` | formatter | Called by daily loop & manual contexts | `padded_emoji_url`, role emojis, summary data | Discord embed with markdown sections & optional thumbnail | Hard-codes bracket order; ignores overflow by concatenating simple text blocks.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L662-L697】 |
| `.../MM/bot_clanmatch_prefix.py::daily_recruiters_update` | scheduled + posting | `@tasks.loop(time=POST_TIME_UTC)`; thread mention | Discord thread IDs via `RECRUITERS_THREAD_ID`, role IDs for pings | Single embed + markdown header message | Skips silently if channel missing; prints to stdout on failure, no retry/backoff; mentions coordinator/scout roles when configured.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L699-L720】 |
| `.../MM/bot_clanmatch_prefix.py::sheets_refresh_scheduler` | scheduled + datasource | Manual `bot.loop.create_task` started on ready | `TIMEZONE`, `REFRESH_TIMES`, `LOG_CHANNEL_ID`; `clear_cache`, `get_rows(True)` warm-up | No direct user output; optional log channel ping | Infinite loop with parsed HH:MM windows; prints failure reason, no jitter/backoff; posts refresh notice if log channel resolves.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L598-L657】 |
| `.../MM/bot_clanmatch_prefix.py::scheduled_cleanup` | scheduled | `@tasks.loop(hours=CLEANUP_EVERY_HOURS)` | Env `CLEANUP_THREAD_IDS`, `CLEANUP_AGE_HOURS`; Discord fetch APIs | Deletes bot-authored messages in target threads | Bulk delete w/ archived-thread reopen fallback; prints counts and continues after per-channel errors.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L1113-L1158】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2140-L2158】 |
| `.../MM/bot_clanmatch_prefix.py::health_prefix` | manual | `!health` / `!status` | `get_ws`, bot latency, event timestamps | Plain-text status line | Role-gated; soft-fails with inline error message; deletes invoking command after responding.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2054-L2081】 |
| `.../MM/bot_clanmatch_prefix.py::reload_cache_cmd` | manual | `!reload` | `clear_cache()`; role gate | Acknowledgement message | Clears sheet cache, enforces admin/lead roles; no warm-up or validation afterward.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2083-L2091】 |

#### Notable excerpts
```python
# AUDIT/.../MM/bot_clanmatch_prefix.py (L123-L143)
def get_rows(force: bool = False):
    if force or _cache_rows is None or (time.time() - _cache_time) > CACHE_TTL:
        ws = get_ws(False)
        _cache_rows = ws.get_all_values()
        _cache_time = time.time()
    return _cache_rows
```
```python
# AUDIT/.../MM/bot_clanmatch_prefix.py (L598-L657)
async def sheets_refresh_scheduler():
    tzname = os.environ.get("TIMEZONE", "Europe/Vienna")
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo("UTC")
        tzname = "UTC"

    REFRESH_ENV = os.environ.get("REFRESH_TIMES", "02:00,10:00,18:00")
    times = _parse_refresh_times(REFRESH_ENV)
    print(f"[sheets-refresh] timezone={tzname} times={times}", flush=True)

    while True:
        now = datetime.now(tz)
        future_today = [now.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in times if
                        now.replace(hour=h, minute=m, second=0, microsecond=0) > now]
        if future_today:
            next_dt = min(future_today)
        else:
            h, m = times[0]
            next_dt = (now + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)

        await _sleep_until(next_dt)

        try:
            clear_cache()
            _ = get_rows(True)  # warm cache immediately
            log_id = int(os.environ.get("LOG_CHANNEL_ID", "0") or "0")
            if log_id:
                ch = bot.get_channel(log_id) or await bot.fetch_channel(log_id)
                if ch:
                    when_local = next_dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                    await ch.send(f"🔄 Sheets auto-refreshed at {when_local} ({tzname})")
            print("[sheets-refresh] refreshed cache", flush=True)
        except Exception as e:
            print(f"[sheets-refresh] failed: {type(e).__name__}: {e}", flush=True)
```
```python
# AUDIT/.../MM/bot_clanmatch_prefix.py (L699-L720)
@tasks.loop(time=POST_TIME_UTC)
async def daily_recruiters_update():
    try:
        if not RECRUITERS_THREAD_ID:
            print("[daily] RECRUITERS_THREAD_ID not set; skipping.")
            return

        thread = bot.get_channel(RECRUITERS_THREAD_ID) or await bot.fetch_channel(RECRUITERS_THREAD_ID)
        if thread is None:
            print(f"[daily] Could not fetch thread {RECRUITERS_THREAD_ID}")
            return

        embed = build_recruiters_summary_embed(getattr(thread, "guild", None))

        parts = [f"# Update {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"]
        if ROLE_ID_RECRUITMENT_COORDINATOR:
            parts.append(f"<@&{ROLE_ID_RECRUITMENT_COORDINATOR}>")
        if ROLE_ID_RECRUITMENT_SCOUT:
            parts.append(f"<@&{ROLE_ID_RECRUITMENT_SCOUT}>")
        content = "\n".join(parts)

        await thread.send(content=content, embed=embed)
    except Exception as e:
        print(f"[daily] post failed: {type(e).__name__}: {e}")
```

### Matchmaker (MM) – `welcome.py`
No reporting loops or embeds beyond thread logging helpers; module focuses on welcome messaging UX and does not emit recruiter reports or scheduled summaries.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py†L1-L120】

### WelcomeCrew (WC) – `bot_welcomecrew.py`
| Path | Type | Entry points | Dependencies | Output shape | Notes |
| --- | --- | --- | --- | --- | --- |
| `.../WC/bot_welcomecrew.py::_load_clan_tags` | datasource + cache | `_load_clan_tags(force)` | `GSHEET_ID`, `CLANLIST_TAB_NAME`, `CLANLIST_TAG_COLUMN`, `CLAN_TAGS_CACHE_TTL_SEC` | List[str] of unique tags; regex cache | Rebuilds regex for tag detection; logs on failure and clears cache; optional preload during setup hook.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L306-L345】 |
| `.../WC/bot_welcomecrew.py::scheduled_refresh_loop` | scheduled + datasource | Manual task (noted near startup) | `REFRESH_TIMES`, `TIMEZONE`, `_load_clan_tags`, `LOG_CHANNEL_ID`; optional sheet warm-up | Channel notification text | 24h rolling loop; warms sheets concurrently; swallows log-channel send failures; prints refresh result or failure reason.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1565-L1615】 |
| `.../WC/bot_welcomecrew.py::cmd_env_check` | manual + toggle audit | `!env_check` | Env toggles (`ENABLE_*`), IDs (`WELCOME_CHANNEL_ID`, etc.) | Markdown bullet list | Masks secrets partially; offers hints when required IDs missing; highlights toggle state.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1096】 |
| `.../WC/bot_welcomecrew.py::cmd_sheetstatus` | manual + datasource | `!sheetstatus` | `get_ws`, service account email, sheet tab envs | Plain-text success/failure line | Parallel sheet fetch; surfaces share email; emits inline error with email reminder when open fails.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1110-L1122】 |
| `.../WC/bot_welcomecrew.py::cmd_backfill` | manual + posting | `!backfill_tickets` | Toggles (`ENABLE_WELCOME_SCAN`, etc.), Discord channel IDs, sheet scanners | Progress message + optional summary + attachment | Spawns progress loop, cancels cleanly; posts optional summary & TXT attachment controlled by env flags; no retry on scan errors beyond exception propagation.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1132-L1188】 |
| `.../WC/bot_welcomecrew.py::cmd_backfill_details` | manual + formatter | `!backfill_details` | `_build_backfill_details_text()` | TXT attachment (diff summary) | Generates timestamped text file; reused by auto-post option in backfill command.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1184-L1203】 |
| `.../WC/bot_welcomecrew.py::cmd_reload` | manual | `!reload` | Clears cached worksheet handles & clan tags; global state | Confirmation text | Full cache reset for Sheets + tag regex; requires manual rebuild on next use.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1234-L1240】 |
| `.../WC/bot_welcomecrew.py::cmd_health` / `cmd_checksheet` | manual | `!health`, `!checksheet` | Sheet fetch, latency, uptime | Plain-text status lines | Health summarises latency + sheet reachability; checksheet counts rows via blocking to-thread calls.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1242-L1270】 |
| `.../WC/bot_welcomecrew.py::render_watch_status_text` | formatter | Used by `!watch_status` | Watch logs, timezone formatting | Markdown bullet list | Shows ON/OFF toggles, latest 5 actions with thread links; depends on log_action calls across watchers.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L696-L724】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1278-L1280】 |

#### Notable excerpts
```python
# AUDIT/.../WC/bot_welcomecrew.py (L306-L345)
def _load_clan_tags(force: bool=False) -> List[str]:
    now = time.time()
    if not force and _clan_tags_cache and (now - _last_clan_fetch < CLAN_TAGS_CACHE_TTL_SEC):
        return _clan_tags_cache

    tags: List[str] = []
    try:
        sh = gs_client().open_by_key(GSHEET_ID)
        ws = sh.worksheet(CLANLIST_TAB_NAME)
        values = ws.get_all_values() or []
        if values:
            header = [h.strip().lower() for h in values[0]] if values else []
            col_idx = None
            for key in ("clantag", "tag", "abbr", "code"):
                if key in header:
                    col_idx = header.index(key)
                    break
            if col_idx is None:
                col_idx = max(0, CLANLIST_TAG_COLUMN - 1)
            for row in values[1:]:
                cell = row[col_idx] if col_idx < len(row) else ""
                t = _normalize_dashes(cell).strip().upper()
                if t:
                    tags.append(t)

        _clan_tags_cache = list(dict.fromkeys(tags))
        _clan_tags_norm_set = { _normalize_dashes(t).upper() for t in _clan_tags_cache }
        _last_clan_fetch = now

        parts = sorted((_normalize_dashes(t).upper() for t in _clan_tags_cache), key=len, reverse=True)
        if parts:
            alt = "|".join(re.escape(p) for p in parts)
            _tag_regex_cache = re.compile(rf"(?<![A-Za-z0-9_])(?:{alt})(?![A-Za-z0-9_])", re.IGNORECASE)
        else:
            _tag_regex_cache = None
    except Exception as e:
        print("Failed to load clanlist:", e, flush=True)
        _clan_tags_cache = []; _clan_tags_norm_set = set(); _tag_regex_cache = None
    return _clan_tags_cache
```
```python
# AUDIT/.../WC/bot_welcomecrew.py (L1565-L1615)
async def scheduled_refresh_loop():
    try:
        tz = ZoneInfo(TIMEZONE) if ZoneInfo else _tz.utc
    except Exception:
        tz = _tz.utc
    times = _parse_times_csv(REFRESH_TIMES)
    print(f"[refresh] TZ={TIMEZONE} times={times}", flush=True)

    while True:
        now = datetime.now(tz)
        today_candidates = [
            now.replace(hour=h, minute=m, second=0, microsecond=0)
            for (h, m) in times
            if now.replace(hour=h, minute=m, second=0, microsecond=0) > now
        ]
        if today_candidates:
            next_dt = min(today_candidates)
        else:
            h, m = times[0]
            next_dt = (now + _td(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)

        await _sleep_until(next_dt)

        try:
            await _run_blocking(_load_clan_tags, True)

            try:
                await asyncio.gather(
                    _run_blocking(get_ws, SHEET1_NAME, HEADERS_SHEET1),
                    _run_blocking(get_ws, SHEET4_NAME, HEADERS_SHEET4),
                )
            except Exception:
                pass

            if LOG_CHANNEL_ID:
                ch = bot.get_channel(LOG_CHANNEL_ID)
                if isinstance(ch, (discord.TextChannel, discord.Thread)):
                    when_local = next_dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                    try:
                        await ch.send(f"🔄 WelcomeCrew: refreshed caches at {when_local} ({TIMEZONE})")
                    except Exception:
                        pass

            print("[refresh] clan tags + sheet handles refreshed", flush=True)
        except Exception as e:
            print(f"[refresh] failed: {type(e).__name__}: {e}", flush=True)
```
```python
# AUDIT/.../WC/bot_welcomecrew.py (L1132-L1188)
@bot.command(name="backfill_tickets")
async def cmd_backfill(ctx):
    if backfill_state["running"]:
        return await ctx.reply("A backfill is already running. Use !backfill_status.", mention_author=False)
    backfill_state["running"] = True; backfill_state["last_msg"] = ""
    progress_msg = await ctx.reply("Starting backfill…", mention_author=False)

    async def progress_loop():
        while backfill_state["running"]:
            try: await progress_msg.edit(content=_render_status())
            except Exception: pass
            await asyncio.sleep(5.0)
    updater_task = asyncio.create_task(progress_loop())

    try:
        async def tick():
            try: await progress_msg.edit(content=_render_status())
            except Exception: pass

        if ENABLE_WELCOME_SCAN and WELCOME_CHANNEL_ID:
            ch = bot.get_channel(WELCOME_CHANNEL_ID)
            if isinstance(ch, discord.TextChannel):
                await scan_welcome_channel(ch, progress_cb=tick)
        if ENABLE_PROMO_SCAN and PROMO_CHANNEL_ID:
            ch2 = bot.get_channel(PROMO_CHANNEL_ID)
            if isinstance(ch2, discord.TextChannel):
                await scan_promo_channel(ch2, progress_cb=tick)
    finally:
        backfill_state["running"] = False
        try: updater_task.cancel()
        except Exception: pass

    await progress_msg.edit(content=_render_status() + "\nDone.")

    if POST_BACKFILL_SUMMARY:
        w = backfill_state["welcome"]; p = backfill_state["promo"]
        def _fmt_list(ids: List[str], max_items=10) -> str:
            if not ids: return "—"
            show = ids[:max_items]; extra = len(ids) - len(show)
            return ", ".join(show) + (f" …(+{extra})" if extra>0 else "")
        msg = (
            "**Backfill report (top 10 each)**\n"
            f"**Welcome** added: {len(w['added_ids'])} — {_fmt_list(w['added_ids'])}\n"
            f"updated: {len(w['updated_ids'])} — {_fmt_list(w['updated_ids'])}\n"
            f"skipped: {len(w['skipped_ids'])} — {_fmt_list(w['skipped_ids'])}\n"
            f"**Promo** added: {len(p['added_ids'])} — {_fmt_list(p['added_ids'])}\n"
            f"updated: {len(p['updated_ids'])} — {_fmt_list(p['updated_ids'])}\n"
            f"skipped: {len(p['skipped_ids'])} — {_fmt_list(p['skipped_ids'])}\n"
        )
        await ctx.send(msg)

    if AUTO_POST_BACKFILL_DETAILS:
        data = _build_backfill_details_text()
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        buf = io.BytesIO(data.encode("utf-8"))
        await ctx.send(file=discord.File(buf, filename=f"backfill_details_{ts}.txt"))
```

## 3) Config & Toggles Map
- **Matchmaker**
  - `GSPREAD_CREDENTIALS`, `GOOGLE_SHEET_ID`, `WORKSHEET_NAME`, `SHEETS_CACHE_TTL_SEC` govern sheet access and caching; absence is logged at boot but not fatal, leading to runtime `get_ws` failures.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L91-L149】
  - Reporting outputs are steered via `RECRUITERS_THREAD_ID`, `ROLE_ID_RECRUITMENT_COORDINATOR`, `ROLE_ID_RECRUITMENT_SCOUT`, `TIMEZONE`, `REFRESH_TIMES`, `LOG_CHANNEL_ID` for scheduling and mentions.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L98-L120】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L598-L657】
  - Cleanup toggles (`CLEANUP_THREAD_IDS`, `CLEANUP_EVERY_HOURS`, `CLEANUP_AGE_HOURS`) control purge cadence; invalid tokens are logged and skipped.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L1100-L1119】

- **WelcomeCrew**
  - Sheet/config envs (`GSHEET_ID`, `SHEET1_NAME`, `SHEET4_NAME`, `CLANLIST_TAB_NAME`, `CLANLIST_TAG_COLUMN`, `GOOGLE_SERVICE_ACCOUNT_JSON`) are surfaced by `!env_check` and `!sheetstatus`, with masked previews for secrets.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L30-L66】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1122】
  - Feature flags (`ENABLE_*`, `AUTO_POST_BACKFILL_DETAILS`, `POST_BACKFILL_SUMMARY`, `ENABLE_NOTIFY_FALLBACK`) gate command availability and watcher behavior; defaults skew to ON except stricter requirements (close markers) which default OFF.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L38-L85】
  - Scheduler tuning via `REFRESH_TIMES`, `TIMEZONE`, `LOG_CHANNEL_ID`, `CLAN_TAGS_CACHE_TTL_SEC`; missing values fall back to UTC timings and 8h TTL.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L30-L66】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1565-L1615】

## 4) Scheduler Patterns
- Matchmaker relies on discord.py `@tasks.loop` for the daily update and cleanup, plus a manual `asyncio` loop for sheet refresh that starts during `on_ready`. The refresh loop parses HH:MM windows once per cycle and lacks jitter or cancellation hooks; tasks restart automatically when `on_ready` fires again.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L598-L720】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L2140-L2158】
- WelcomeCrew mirrors the manual loop approach for cache refreshes, including time parsing and channel notifications. Other reporting commands are manual, but backfill progress creates its own async task to refresh UI every five seconds; watchdog loops (`@tasks.loop`) exist for health but are unrelated to reporting outputs.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1132-L1188】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1565-L1615】
- Footguns: both schedulers assume a warm Discord connection; neither handles overlapping iterations or cancellation on shutdown. Cache refreshers run immediately after boot, which may race sheet availability if credentials lag.

## 5) Caches & Staleness Handling
- Matchmaker sheet cache (`get_rows`) maintains a single snapshot until TTL expires or manual `clear_cache` runs; the daily loop always reads cached data, so stale rows persist up to TTL unless the refresh scheduler succeeds. Failures in refresh leave old data without fallback messaging.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L136-L149】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L598-L657】
- WelcomeCrew caches clan tags with an 8h TTL and rebuilds a regex for fast matching; `_load_clan_tags` clears caches on errors. `!reload` wipes sheet and tag caches, forcing recomputation on demand. Backfill trackers store interim results in memory only, reset on command completion.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L306-L345】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1234-L1240】
- Neither stack keeps “last good snapshot” artifacts; they rely on successful sheet pulls during each run.

## 6) Posting Pipeline
- Matchmaker resolves target threads and role mentions from env IDs, building markdown headers plus a single embed. Failures to fetch the thread or send the message are logged to stdout only, so Discord recipients are unaware of skips.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L699-L720】
- WelcomeCrew commands reply directly in invoking channels, with optional follow-up attachments for backfill detail dumps; scheduler notifications post to a configured log channel using timezone-adjusted timestamps. Notification fallbacks mention roles when configured.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1132-L1188】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1565-L1615】
- Rate limiting: Matchmaker cleanup uses bulk delete with fallback iteration; WelcomeCrew’s backfill throttles sheet writes elsewhere but reporting posts have no explicit rate limiting beyond Discord library defaults.

## 7) Reusable Formatters
- Matchmaker offers `build_recruiters_summary_embed` plus various paging helpers for search results; the summary embed uses simple markdown sections without truncation logic beyond Discord’s default limits.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L662-L697】
- WelcomeCrew’s `render_watch_status_text` and `_build_backfill_details_text` produce markdown or TXT bodies summarizing watcher actions and backfill diffs. `cmd_env_check` assembles bullet lists with masked secrets. None enforce strict length caps, relying on human-scale outputs.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1188】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L696-L724】

## 8) Gaps vs Phase 6 goal
- **What we can reuse immediately:**
  - Matchmaker’s recruiter summary embed + daily loop provides a ready-made skeleton for “Daily Recruiter Update,” including role mentions and sheet cache management.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L598-L720】
  - WelcomeCrew’s env-audit and sheet status commands could underpin manual “report health” checks, while backfill detail attachment logic shows how to package diagnostics for review.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1203】

- **What needs adaptation:**
  - Both loops need robust error surfacing (Discord notifications, retries) and integration with shared cache services rather than module-level globals. Scheduler start/stop should align with bot lifecycle controls.
  - Embed text should be parameterized to accept new metrics; sheet parsing should leverage typed adapters instead of positional heuristics.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L566-L691】

- **What’s missing entirely:**
  - Feature flags for enabling/disabling the daily report pipeline holistically; Matchmaker lacks a `FEATURE_*` gate around the loop.
  - Graceful stale-data fallbacks (e.g., posting “data stale” notice) and telemetry hooks; neither bot reports metrics beyond stdout logs.

## 9) Risk & Migration Notes
- Heavy reliance on env wiring means misconfiguration silently disables outputs (e.g., unset thread IDs, missing log channel). Incorporate validation during boot to fail fast.【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py†L699-L720】【F:AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py†L1022-L1096】
- Sheet schema coupling (column indices, header names) risks breakage during worksheet migrations; plan to centralize adapters before Phase 6.
- Migration sequence suggestion: extract shared scheduler & cache utilities, wrap existing commands as reference implementations, then incrementally swap in new data sources while keeping legacy loops disabled behind toggles.

## 10) Quick References
- `rg -n "build_recruiters_summary" AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py`
- `rg -n "@tasks.loop" AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/bot_clanmatch_prefix.py`
- `rg -n "@bot.command" AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py`
- `rg -n "REFRESH" AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC/bot_welcomecrew.py`
- `find AUDIT/legacy/clanmatch-welcomecrew -name '*.py'`
