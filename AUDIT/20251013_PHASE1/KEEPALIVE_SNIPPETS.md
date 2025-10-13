# Gateway Keepalive Snippets

## AUDIT/20251010_src/MM/bot_clanmatch_prefix.py#L2044-L2081
```python
# ------------------- Health / reload -------------------
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    # react-only liveness check
    try:
        await ctx.message.add_reaction("🏓")
    except Exception:
        pass


@bot.command(name="health", aliases=["status"])
async def health_prefix(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not _allowed_admin_or_lead(ctx.author):
        await ctx.reply("⚠️ Only **Recruitment Lead** or Admins can use `!health`.", mention_author=False)
        return
    try:
        try:
            ws = get_ws(False)
            _ = ws.row_values(1)
            sheets_status = f"OK (`{WORKSHEET_NAME}`)"
        except Exception as e:
            sheets_status = f"ERROR: {type(e).__name__}"

        latency_ms = round(bot.latency * 1000) if bot.latency is not None else -1
        last_event_age = int(_now() - _LAST_EVENT_TS) if _LAST_EVENT_TS else None
        connected = "🟢 connected" if BOT_CONNECTED else "🔴 disconnected"

        parts = [
            f"{connected}",
            f"Latency: {latency_ms} ms",
            f"Sheets: {sheets_status}",
            f"Uptime: {_fmt_uptime()}",
            f"Last event age: {last_event_age}s" if last_event_age is not None else "Last event age: —",
        ]
        await ctx.reply(" | ".join(parts), mention_author=False)
        await _safe_delete(ctx.message)
    except Exception as e:
        await ctx.reply(f"⚠️ Health error: `{type(e).__name__}: {e}`", mention_author=False)
```

## AUDIT/20251010_src/MM/bot_clanmatch_prefix.py#L2161-L2297
```python
# ------------------- Events -------------------
@bot.event
async def on_socket_response(payload):
    _mark_event()

@bot.event
async def on_connect():
# ADD these two lines if you already have on_connect()
    global BOT_CONNECTED
    BOT_CONNECTED = True
    _mark_event()

@bot.event
async def on_resumed():
# ADD this event; or merge into existing if present
    global BOT_CONNECTED
    BOT_CONNECTED = True
    _mark_event()
# optional: log.info("Gateway resumed")

@bot.event
async def on_ready():
    global BOT_CONNECTED, _LAST_READY_TS
    BOT_CONNECTED = True
    _LAST_READY_TS = _now()
    _mark_event()
# start watchdog once
    try:
        if not _watchdog.is_running():
            _watchdog.start()
    except NameError:
        pass
    print(f"[ready] Logged in as {bot.user} ({bot.user.id})", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"[slash] synced {len(synced)} commands", flush=True)
    except Exception as e:
        print(f"[slash] sync failed: {e}", flush=True)

# kick off the daily poster (safe to call repeatedly)
    if not daily_recruiters_update.is_running():
        daily_recruiters_update.start()

# Start scheduled cleanup
    if not scheduled_cleanup.is_running():
        scheduled_cleanup.start()

# Start the watchdog loop (exits the process if Discord stays disconnected)
    try:
        if not _watchdog.is_running():
            _watchdog.start()
    except NameError:
        pass

# Start the Sheets refresh scheduler (3x/day via REFRESH_TIMES)
    global _SHEETS_REFRESH_TASK
    if _SHEETS_REFRESH_TASK is None or _SHEETS_REFRESH_TASK.done():
        _SHEETS_REFRESH_TASK = bot.loop.create_task(sheets_refresh_scheduler())

# --- Welcome module wiring (discord.py v2: add_cog is async) ---
    global _WELCOME_ADDED, _WELCOME_PRIMED
    if not _WELCOME_ADDED:
        try:
            await bot.add_cog(welcome_cog)
            _WELCOME_ADDED = True
            print("[welcome] cog added", flush=True)
        except Exception as e:
            print(f"[welcome] add_cog failed: {type(e).__name__}: {e}", flush=True)

    if not _WELCOME_PRIMED:
        try:
            await welcome_cog.reload_templates()
            _WELCOME_PRIMED = True
            print("[welcome] templates loaded", flush=True)
        except Exception as e:
            print(f"[welcome] initial template load failed: {type(e).__name__}: {e}", flush=True)

# --- DEBUG: list loaded commands & confirm welcome registration ---
    try:
        names = sorted([c.name for c in bot.commands])
        print("[debug] loaded prefix commands:", ", ".join(names), flush=True)
        if "welcome" not in names:
            print("[debug] WARNING: 'welcome' command not registered", flush=True)
        else:
            print("[debug] OK: 'welcome' command is registered", flush=True)
    except Exception as e:
        print(f"[debug] command list error: {type(e).__name__}: {e}", flush=True)


@bot.event
async def on_disconnect():
    global BOT_CONNECTED, _LAST_DISCONNECT_TS
    BOT_CONNECTED = False
    _LAST_DISCONNECT_TS = _now()

# ------------------- WATCHDOG -------------------

WATCHDOG_CHECK_SEC = int(os.environ.get("WATCHDOG_CHECK_SEC", "60"))
WATCHDOG_MAX_DISCONNECT_SEC = int(os.environ.get("WATCHDOG_MAX_DISCONNECT_SEC", "600"))  # 10 min

async def _maybe_restart(reason: str):
    try:
        log.warning(f"[WATCHDOG] Restarting: {reason}")
    except NameError:
        print(f"[WATCHDOG] Restarting: {reason}")
    try:
        await bot.close()
    finally:
        sys.exit(1)

@tasks.loop(seconds=WATCHDOG_CHECK_SEC)
async def _watchdog():
    now = _now()

# If connected, check for zombie state (no events for a long while + bad latency)
    if BOT_CONNECTED:
        idle_for = (now - _LAST_EVENT_TS) if _LAST_EVENT_TS else 0
        try:
            latency = getattr(bot, "latency", None)
        except Exception:
            latency = None

# 10 min without any events is suspicious; adjust to your traffic level.
        if _LAST_EVENT_TS and idle_for > 600 and (latency is None or latency > 10):
            await _maybe_restart(f"zombie: no events for {int(idle_for)}s, latency={latency}")
        return

# Disconnected: measure real outage time from the last disconnect moment
    global _LAST_DISCONNECT_TS
    if not _LAST_DISCONNECT_TS:
        # first time we noticed the disconnect — start the timer
        _LAST_DISCONNECT_TS = now
        return

    down_for = now - _LAST_DISCONNECT_TS
    if down_for > WATCHDOG_MAX_DISCONNECT_SEC:
        await _maybe_restart(f"disconnected too long: {int(down_for)}s")
```

## AUDIT/20251010_src/MM/bot_clanmatch_prefix.py#L2303-L2349
```python
# ------------------- Tiny web server + image-pad proxy -------------------

def _last_event_age_s() -> int | None:
    return int(_now() - _LAST_EVENT_TS) if _LAST_EVENT_TS else None

async def _health_json(_req):
# 200 when connected; 503 when disconnected; 206 “partial” if zombie hint
    connected = BOT_CONNECTED
    age = _last_event_age_s()
    latency = None
    try:
        latency = getattr(bot, "latency", None)
        if latency is not None:
            latency = float(latency)
    except Exception:
        latency = None

    status = 200 if connected else 503
    # Heuristic: connected but no events for >600s and latency None/huge → partial
    if connected and age is not None and age > 600 and (latency is None or latency > 10):
        status = 206  # “partial content” -> signals zombie-ish to your monitor

    body = {
        "ok": connected,
        "connected": connected,
        "uptime": _fmt_uptime(),
        "last_event_age_s": age,
        "latency_s": latency,
    }
    return web.json_response(body, status=status)

async def _health_json_ok_always(_req):
# Same payload as _health_json, but always HTTP 200 to avoid host flaps.
    connected = BOT_CONNECTED
    age = _last_event_age_s()
    try:
        latency = getattr(bot, "latency", None)
        latency = float(latency) if latency is not None else None
    except Exception:
        latency = None
    body = {
        "ok": connected,
        "connected": connected,
        "uptime": _fmt_uptime(),
        "last_event_age_s": age,
        "latency_s": latency,
        "strict_probe": STRICT_PROBE,
    }
    return web.json_response(body, status=200)
```

## AUDIT/20251010_src/MM/bot_clanmatch_prefix.py#L2465-L2495
```python
async def start_webserver():
    app = web.Application()
    app["session"] = ClientSession()
    async def _close_session(app):
        await app["session"].close()
    app.on_cleanup.append(_close_session)

# Platform-safe defaults:
# - When STRICT_PROBE=0 (default): `/`, `/ready`, `/health` always 200
# - When STRICT_PROBE=1: platform probes use deep status (200/206/503)
    if STRICT_PROBE:
        app.router.add_get("/", _health_json)
        app.router.add_get("/ready", _health_json)
        app.router.add_get("/health", _health_json)
    else:
        app.router.add_get("/", _health_json_ok_always)
        app.router.add_get("/ready", _health_json_ok_always)
        app.router.add_get("/health", _health_json_ok_always)

# Deep health endpoint for your monitoring/alerts (can return 206 on zombie-ish)
    app.router.add_get("/healthz", _health_json)

# Existing emoji pad proxy
    app.router.add_get("/emoji-pad", emoji_pad_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[keepalive] HTTP server listening on :{port} | STRICT_PROBE={int(STRICT_PROBE)}", flush=True)
```

## AUDIT/20251010_src/MM/bot_clanmatch_prefix.py#L2529-L2544
```python
# ------------------- Boot both -------------------
async def main():
    try:
        asyncio.create_task(start_webserver())
        token = os.environ.get("DISCORD_TOKEN", "").strip()
        if not token or len(token) < 50:
            raise RuntimeError("Missing/short DISCORD_TOKEN.")
        print("[boot] starting discord bot…", flush=True)
        await bot.start(token)
    except Exception as e:
        print("[boot] FATAL:", e, flush=True)
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1098-L1105
```python
@bot.command(name="ping")
@cmd_enabled(ENABLE_CMD_PING)
async def ping(ctx):
    # react-only liveness check
    try:
        await ctx.message.add_reaction("🏓")
    except Exception:
        pass
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1242-L1251
```python
@bot.command(name="health")
@cmd_enabled(ENABLE_CMD_HEALTH)
async def cmd_health(ctx):
    lat = int(bot.latency*1000)
    try:
        ws1 = await _run_blocking(get_ws, SHEET1_NAME, HEADERS_SHEET1)
        ok = f"🟢 OK ({ws1.title})"
    except Exception:
        ok = "🔴 FAILED"
    await ctx.reply(f"🟢 Bot OK | Latency: {lat} ms | Sheets: {ok} | Uptime: {uptime_str()}", mention_author=False)
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1272-L1276
```python
@bot.command(name="reboot")
@cmd_enabled(ENABLE_CMD_REBOOT)
async def cmd_reboot(ctx):
    await ctx.reply("Rebooting…", mention_author=False)
    await asyncio.sleep(1.0); os._exit(0)
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1397-L1471
```python
# ---------- LIVE WATCHERS ----------
@bot.event
async def on_socket_response(_payload):
    _mark_event()

@bot.event
async def on_connect():
    global BOT_CONNECTED
    BOT_CONNECTED = True
    _mark_event()

@bot.event
async def on_resumed():
    global BOT_CONNECTED
    BOT_CONNECTED = True
    _mark_event()

@bot.event
async def on_ready():
    global BOT_CONNECTED, _LAST_READY_TS
    BOT_CONNECTED = True
    _LAST_READY_TS = _now()
    _mark_event()
# start watchdog once
    try:
        if not _watchdog.is_running():
            _watchdog.start()
    except NameError:
        pass

# start the 3×/day cache refresh (idempotent)
    global _refresh_task
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = bot.loop.create_task(scheduled_refresh_loop())


@bot.event
async def on_disconnect():
    global BOT_CONNECTED, _LAST_DISCONNECT_TS
    BOT_CONNECTED = False
    _LAST_DISCONNECT_TS = _now()

async def _maybe_restart(reason: str):
    try:
        print(f"[WATCHDOG] Restarting: {reason}", flush=True)
    finally:
        try:
            await bot.close()
        finally:
            sys.exit(1)

@tasks.loop(seconds=WATCHDOG_CHECK_SEC)
async def _watchdog():
    now = _now()

    if BOT_CONNECTED:
        idle_for = (now - _LAST_EVENT_TS) if _LAST_EVENT_TS else 0
        try:
            latency = float(getattr(bot, "latency", 0.0)) if bot.latency is not None else None
        except Exception:
            latency = None

# If connected but no events for >10m and latency missing/huge → likely zombied gateway
        if _LAST_EVENT_TS and idle_for > 600 and (latency is None or latency > 10):
            await _maybe_restart(f"zombie: no events {int(idle_for)}s, latency={latency}")
        return

# Disconnected: count real downtime since last disconnect
    global _LAST_DISCONNECT_TS
    if not _LAST_DISCONNECT_TS:
        _LAST_DISCONNECT_TS = now
        return

    if (now - _LAST_DISCONNECT_TS) > WATCHDOG_MAX_DISCONNECT_SEC:
        await _maybe_restart(f"disconnected too long: {int(now - _LAST_DISCONNECT_TS)}s")
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1473-L1511
```python
async def _health_json(_req):
# Deep status: 200 if connected, 503 if disconnected, 206 if "zombie-ish"
    connected = BOT_CONNECTED
    age = _last_event_age_s()
    try:
        latency = float(bot.latency) if bot.latency is not None else None
    except Exception:
        latency = None

    status = 200 if connected else 503
    if connected and age is not None and age > 600 and (latency is None or latency > 10):
        status = 206

    body = {
        "ok": connected,
        "connected": connected,
        "uptime": uptime_str(),
        "last_event_age_s": age,
        "latency_s": latency,
    }
    return web.json_response(body, status=status)

async def _health_json_ok_always(_req):
# Same payload as above, but **always** HTTP 200 (prevents platform flaps)
    connected = BOT_CONNECTED
    age = _last_event_age_s()
    try:
        latency = float(bot.latency) if bot.latency is not None else None
    except Exception:
        latency = None
    body = {
        "ok": connected,
        "connected": connected,
        "uptime": uptime_str(),
        "last_event_age_s": age,
        "latency_s": latency,
        "strict_probe": STRICT_PROBE,
    }
    return web.json_response(body, status=200)
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1513-L1538
```python
async def start_webserver():
    app = web.Application()
    app["session"] = ClientSession()
    async def _close_session(app):
        await app["session"].close()
    app.on_cleanup.append(_close_session)

# If STRICT_PROBE=0 (default): / and /ready always 200 to avoid flaps
    if STRICT_PROBE:
        app.router.add_get("/", _health_json)
        app.router.add_get("/ready", _health_json)
        app.router.add_get("/health", _health_json)
    else:
        app.router.add_get("/", _health_json_ok_always)
        app.router.add_get("/ready", _health_json_ok_always)
        app.router.add_get("/health", _health_json_ok_always)

# Deep check for Render’s Health Check Path
    app.router.add_get("/healthz", _health_json)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[keepalive] HTTP server on :{port} | STRICT_PROBE={int(STRICT_PROBE)}", flush=True)
```

## AUDIT/20251010_src/WC/bot_welcomecrew.py#L1804-L1812
```python
# ------------------------ start -----------------------
async def _boot():
    if not TOKEN or len(TOKEN) < 20:
        raise RuntimeError("Missing/short DISCORD_TOKEN.")
    asyncio.create_task(start_webserver())
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(_boot())
```
