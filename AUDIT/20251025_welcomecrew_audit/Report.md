# WelcomeCrew Legacy Audit (2025-10-25)

## 1) Flow Diagram (textual)
- **Ticket opened → thread lifecycle**
  - Bot auto-joins new welcome/promo threads under configured parents to ensure visibility: 
    ```py
        if thread.parent_id in {WELCOME_CHANNEL_ID, PROMO_CHANNEL_ID}:
            await thread.join()
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1630-L1631】
  - Watchers only process messages inside target threads; mentions trigger a join if needed:
    ```py
        if th.parent_id in {WELCOME_CHANNEL_ID, PROMO_CHANNEL_ID}:
            if bot.user and bot.user.mentioned_in(message):
                try: await th.join()
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1660-L1663】
- **Close detection → tag capture**
  - Message listener scans for "Ticket closed by …" markers; parses thread name for ticket/user/tag and logs an action:
    ```py
            if is_close_marker(text):
                parsed = parse_welcome_thread_name_allow_missing(th.name or "")
                if parsed:
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1668-L1670】
  - If no tag parsed, thread is staged in `_pending_*`; recruiters can reply with tag text before archive completes:
    ```py
                        _pending_welcome[th.id] = {"ticket": ticket, "username": username, "close_dt": close_dt}
                elif th.id in _pending_welcome:
                    if not message.author.bot:
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1677-L1682】
- **Archive/lock → placement**
  - `on_thread_update` fires when threads archive/lock; re-parses names, infers close timestamp, and either finalizes placement (rename + Sheets write) or prompts via dropdown if tag missing:
    ```py
        close_dt = close_dt or await find_close_timestamp(after)
        await _finalize_welcome(after, ticket, username, tag or "", close_dt)
        await _finalize_promo(after, ticket, username, tag or "", close_dt)
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1747-L1756】
- **Prompt delivery → fallback**
  - Tag picker DM is avoided; bot posts dropdown inside thread, falling back to notify channel ping if posting fails:
    ```py
    view = TagPickerView(mode, thread, ticket, username, tags)
    sent = await thread.send(content, view=view, suppress_embeds=True)
    await _notify_channel(thread.guild, f"{prefix}Need clan tag for **{username}** …")
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L783-L804】
- **Completion**
  - `_finalize_*` writes ticket row, renames to `Closed-####-username-TAG`, and logs to in-memory watch log (used by `!watch_status`):
    ```py
        ws = await _run_blocking(get_ws, SHEET1_NAME, HEADERS_SHEET1)
        status = await _run_blocking(upsert_welcome, SHEET1_NAME, ws, ticket, row, dummy_bucket)
        log_action("welcome", "logged", ticket=_fmt_ticket(ticket), username=username, clantag=clantag or "", status=status, link=thread_link(thread))
    ```
    【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L831-L839】

## 2) Commands, Buttons, Watchers

### Commands
| Name | Trigger & perms | Side effects | Channel/role dependencies |
| --- | --- | --- | --- |
| `help` | Prefix `!help` (no extra perms) | Sends mobile-friendly embed with command list and watcher status.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L191-L237】 | Uses optional `HELP_ICON_URL` env; no fixed IDs. |
| Slash `help` | Slash command (global sync at boot) | Sends same embed ephemerally.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L238-L257】 | Requires successful `bot.tree.sync()` at startup.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L258-L266】 |
| `env_check` | `!env_check`; open to any user | Lists required env vars, toggles, hints.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1022-L1078】 | Implicit knowledge of required IDs and env names. |
| `ping` | `!ping`; gated by `ENABLE_CMD_PING` | Adds 🏓 reaction for liveness check.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1098-L1104】 | None. |
| `sheetstatus` | `!sheetstatus`; `ENABLE_CMD_SHEETSTATUS` | Opens configured worksheets, reports tab names, service account email, warns on failure.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1131】 | Depends on env sheet IDs; surfaces `CLANLIST_TAB_NAME`. |
| `backfill_tickets` | `!backfill_tickets`; `ENABLE_CMD_BACKFILL` | Runs welcome/promo scans, posts progress edits, optional summary + details file.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1132-L1182】 | Needs channel IDs, Sheets access; uses env toggles for scan enable. |
| `backfill_stop` | `!backfill_stop` | Halts running backfill loop, updates status message.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1184-L1196】 | None beyond backfill context. |
| `backfill_details` | `!backfill_details` | Sends text file of diffs/skip reasons from last run.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1198-L1204】 | None. |
| `clan_tags_debug` | `!clan_tags_debug` | Forces clanlist reload, reports count/sample, flag for `F-IT`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1206-L1213】 | Needs Sheets + clanlist tab. |
| `dedupe_sheet` | `!dedupe_sheet`; `ENABLE_CMD_DEDUPE` | Removes duplicate ticket rows (with optional type key).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1214-L1233】 | Writes to both sheets. |
| `reload` | `!reload`; `ENABLE_CMD_RELOAD` | Clears cached worksheets, clan tags, client; next access reconnects.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1234-L1240】 | None. |
| `health` | `!health`; `ENABLE_CMD_HEALTH` | Reports latency, Sheets reachability, uptime.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1242-L1251】 | Needs Sheets access. |
| `checksheet` | `!checksheet`; `ENABLE_CMD_CHECKSHEET` | Counts rows in welcome/promo tabs.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1253-L1264】 | Requires Sheets read. |
| `reboot` | `!reboot`; `ENABLE_CMD_REBOOT` | Replies then exits process (os._exit).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1266-L1273】 | None. |
| `watch_status` | `!watch_status` | Posts watcher ON/OFF and last five actions.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1278-L1284】 | Relies on in-memory `WATCH_LOG`. |

**Key command implementations (snippets):**
- Help menu reply gate:
  ```py
  @bot.command(name="help")
  async def help_cmd(ctx, *, topic: str = None):
      if not topic: return await ctx.reply(embed=_mk_help_embed_mobile(ctx.guild), mention_author=False)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L237-L257】
- Sheets status probe:
  ```py
  @bot.command(name="sheetstatus")
  async def cmd_sheetstatus(ctx):
      await ctx.reply(
          f"✅ Sheets OK: **{title}**\n• Tabs: `{SHEET1_NAME}`, `{SHEET4_NAME}`, `{CLANLIST_TAB_NAME}` (tags col {CLANLIST_TAG_COLUMN})\n• Share with: `{email}`",
          mention_author=False
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1119】
- Backfill controller:
  ```py
  @bot.command(name="backfill_tickets")
  async def cmd_backfill(ctx):
      progress_msg = await ctx.reply("Starting backfill…", mention_author=False)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1132-L1182】
- Dedupe executor:
  ```py
  @bot.command(name="dedupe_sheet")
  async def cmd_dedupe(ctx):
      ws1, ws4 = await asyncio.gather(
          _run_blocking(get_ws, SHEET1_NAME, HEADERS_SHEET1),
          _run_blocking(get_ws, SHEET4_NAME, HEADERS_SHEET4),
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1216-L1223】
- Reboot shortcut (risk):
  ```py
  @bot.command(name="reboot")
  async def cmd_reboot(ctx):
      await asyncio.sleep(1.0); os._exit(0)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1272-L1277】

### Buttons & Dropdowns
| UI element | Trigger | Side effects | Dependencies |
| --- | --- | --- | --- |
| `TagPickerView` select | Recruiter chooses tag from dropdown (per-thread view) | Finalizes welcome/promo (rename + Sheets upsert), acknowledges success, disables controls.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L788-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L830-L859】 | Requires clan tag cache; thread must remain accessible. |
| `TagPickerView` pager buttons | Prev/Next buttons for >25 tags | Updates dropdown page in-place.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L812-L842】 | None beyond tag list. |
| `TagPickerReloadView` button | Offered after timeout | Reinstantiates picker without re-pinging; checks pending-state guard.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L704-L737】 | Depends on `_pending_*` state. |

**UI control snippets:**
- Dropdown send + caching handle:
  ```py
  view = TagPickerView(mode, thread, ticket, username, tags)
  sent = await thread.send(content, view=view, suppress_embeds=True)
  view.message = sent
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L783-L787】
- Reload button guard:
  ```py
  if self.original.thread.id not in pending:
      await interaction.response.edit_message(content="Already logged — picker closed.", view=None)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1293-L1307】

### Watchers / Background Tasks
| Listener/task | Trigger | Action | Dependencies |
| --- | --- | --- | --- |
| `on_thread_create` | New thread under welcome/promo | Auto-joins thread to enable posts.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1626-L1633】 | Channel IDs. |
| `on_message` | Any thread message | Detects close markers, stages pending tags, accepts manual tag replies, sends confirmations.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1645-L1721】 | Needs thread naming convention; clan tag detection. |
| `on_thread_update` | Thread archived/locked | Re-finalizes or prompts on close transition; clears pending on reopen.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1726-L1800】 | Channel IDs; watchers toggles. |
| `_watchdog` task | Interval per `WATCHDOG_CHECK_SEC` | Restarts process if idle or disconnected too long.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1449-L1498】 | Env thresholds. |
| `scheduled_refresh_loop` | Times from `REFRESH_TIMES` | Reloads clan tags, optionally warms sheets, logs to channel.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1540-L1615】 | ZoneInfo availability, LOG channel optional. |
| Keepalive web server | Boot if `ENABLE_WEB_SERVER` | Exposes `/health` variants for probes, with strict/soft responses.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1489-L1538】 | PORT env; aiohttp. |

**Watcher snippets:**
- Close marker handling:
  ```py
  if is_close_marker(text):
      parsed = parse_welcome_thread_name_allow_missing(th.name or "")
      if parsed:
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1668-L1670】
- Pending tag text capture:
  ```py
  if th.id in _pending_welcome and not message.author.bot:
      tag = _match_tag_in_text(_aggregate_msg_text(message))
      if tag:
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1680-L1684】
- Watchdog exit path:
  ```py
  if _LAST_EVENT_TS and idle_for > 600 and (latency is None or latency > 10):
      await _maybe_restart(f"zombie: no events {int(idle_for)}s, latency={latency}")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1459-L1462】

## 3) Data Touchpoints

### Google Sheets
| Function / Command | Tab(s) | Operation | Notes |
| --- | --- | --- | --- |
| `get_ws` | Configured tab names (`SHEET1_NAME`, `SHEET4_NAME`, `CLANLIST_TAB_NAME`) | Opens worksheet, creates if missing, enforces header row.| Default tab titles fallback to `Sheet1`/`Sheet4`/`clanlist`; overwrites header row if mismatch.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L139-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L122】 |
| `_load_clan_tags` | Clanlist tab | Reads all values, infers tag column by header or configured index; builds regex cache.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L320-L356】 | Assumes header contains variants of tag name or uses numeric column fallback. |
| `upsert_welcome` | Welcome tab | Row update/append with throttling/backoff; logs diffs to state bucket.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L469】 | Expects ticket number in column A; relies on `_index_simple`. |
| `upsert_promo` | Promo tab | Update/append keyed by ticket+type+created; logs diffs.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L470-L489】 | Secondary scan `_find_promo_row_pair` tries best-effort match.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L456-L469】 |
| `dedupe_sheet` | Welcome & Promo | Deletes duplicates keeping latest date; writes via `ws.delete_rows`.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L490-L517】 | Requires date parse format `YYYY-MM-DD HH:MM`. |
| Backfill scans | Welcome & Promo | Iterates open/archived threads, writes via upsert, collects skip reasons.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L861-L919】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L920-L959】 | Maintains `backfill_state`. |
| Commands (`sheetstatus`, `checksheet`, etc.) | Both tabs | Read-only verification (row counts, health).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1107-L1264】 | None. |

**Sheet access snippets:**
- Worksheet fetch + header enforcement:
  ```py
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L143-L146】
- Header overwrite when mismatch:
  ```py
            if [h.strip().lower() for h in head] != [h.strip().lower() for h in want_headers]:
                ws.update("A1", [want_headers])
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L150-L153】
- Clan tag column discovery:
  ```py
                if key in header:
                    col_idx = header.index(key)
                    break
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L320-L323】
- Tag normalization per row:
  ```py
                cell = row[col_idx] if col_idx < len(row) else ""
                t = _normalize_dashes(cell).strip().upper()
                if t: tags.append(t)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L327-L333】
- Welcome row upsert:
  ```py
  row = [_fmt_ticket(ticket), username, clantag or "", date_str]
  status = await _run_blocking(upsert_welcome, SHEET1_NAME, ws, ticket, row, dummy_bucket)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L834-L839】

### Other State
- In-memory caches for worksheets, indices, clan tags, and backfill metrics (`_ws_cache`, `_index_simple`, `_index_promo`, `_clan_tags_cache`, `backfill_state`).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L116-L143】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L417-L431】
- Pending placement dictionaries `_pending_welcome` / `_pending_promo` keyed by thread ID until tag chosen.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1617-L1618】
- `WATCH_LOG` deque holds last 50 actions for status reporting.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L660-L709】
- No persistent files beyond generated backfill detail attachments (sent as ephemeral file objects).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1186-L1204】

Embedded assumptions:
- Sheet headers hard-coded to specific column names; code overwrites mismatches silently.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】
- Ticket numbers must be four digits with leading zeros (`_fmt_ticket`).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L303-L311】
  ```py
  _pending_welcome: Dict[int, Dict[str, Any]] = {}
  WATCH_LOG = deque(maxlen=50)
  def _fmt_ticket(s: str) -> str:
      return (s or "").strip().lstrip("#").zfill(4)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1617-L1618】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L689-L698】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L303-L304】

## 4) Output Artifacts
- **Help embed** with sections for user actions, command list, watcher status; optional thumbnail via env.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L191-L231】
- **Tag prompt message** (`Which clan tag for …`) plus dropdown UI, with timeout message offering reload.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L842-L858】
- **Success acknowledgment** (`Got it — set clan tag…`) sent after tag selection or textual reply.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L786-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1688-L1695】
- **Watcher status text** summarizing ON/OFF and recent actions for `!watch_status` and help embed.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L700-L724】
- **Backfill summary** optional plain-text message and attached details file enumerating diffs/skips.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1163-L1182】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1186-L1204】
- **Refresh log ping** to `LOG_CHANNEL_ID` when clan tags reload.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1603-L1611】

**Representative output snippets:**
- Help embed copy:
  ```py
  e.add_field(name="User Actions — Recruiters & Mods", value="On Close Ticket… I rename the thread to **`Closed-####-username-TAG`**…")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L200-L207】
- Tag prompt message:
  ```py
  content = f"Which clan tag for **{username}** (ticket **{_fmt_ticket(ticket)}**)?\nPick one from the menu below…"
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L776-L781】
- Success ack text:
  ```py
  await th.send(f"Got it — set clan tag to **{tag}** and logged to the sheet. ✅")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1688-L1691】
- Watcher status format:
  ```py
  lines = [f"👀 **Watchers**: {on} (welcome={on_w}, promo={on_p})"]
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L700-L705】

## 5) Error Handling
- Sheets access uses `_with_backoff` for transient API errors and `_sleep_ms` throttle; errors recorded in state buckets and printed to stdout.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L168-L180】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L489】
- Failure to post prompts falls back to notify channel; if notify fails, silently drops (returns False).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L736-L746】
- Command errors bubble to user with generic `⚠️ Command error…` except unknown commands silently ignored.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1635-L1642】
- Watchdog restarts process if no events or long disconnect; `_maybe_restart` exits after closing bot.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1449-L1498】
- Missing env like `DISCORD_TOKEN`, `GSHEET_ID`, or service account raises runtime errors at boot (no fail-soft path).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L141】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1805-L1812】

**Error-path snippets:**
- Backoff helper:
  ```py
  if transient and attempt < 5:
      _sleep_ms(int(delay * 1000 + random.randint(0, 200)))
      delay = min(delay * 2, 8.0)
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L168-L179】
- Notify fallback return:
  ```py
  try: await ch.send(content); return True
  except Exception: return False
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L736-L746】
- Command error surfacing:
  ```py
  await ctx.reply(f"⚠️ Command error: `{type(error).__name__}: {error}`")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1635-L1641】
- Hard stop on missing token:
  ```py
  if not TOKEN or len(TOKEN) < 20: raise RuntimeError("Missing/short DISCORD_TOKEN.")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1805-L1808】

## 6) Gaps vs. New Guardrails
| Guardrail | Status | Evidence |
| --- | --- | --- |
| No hard-coded IDs | **Compliant (with caveats)** | Channel/role IDs pulled from env, defaulting to `0`; however sheet tab names default to literals (`Sheet1`, `Sheet4`, `clanlist`), so configuration must override for non-legacy setups.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L88】 |
| Fail-soft external I/O | **Non-compliant** | Missing env values raise and abort boot; Sheets errors during finalize print but still mark placement status as "error" with no retry beyond backoff.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L139-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L489】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1805-L1812】 |
| Public APIs only | **Compliant** | Uses Discord bot APIs, slash commands, channel posts, and Google Sheets via gspread; notify fallback stays within configured channels (no DMs or hidden transports).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L139-L156】 |
| Documentation hooks | **Non-compliant** | Help embed documents runtime behavior, but no link to external specs or ADR references; relies entirely on inline copy.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L191-L231】 |
| Feature flags respected | **Compliant** | Every command/watch/backfill path gated by `ENABLE_*` toggles; watchers check both global and scope-specific flags.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L55-L88】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1699】 |
| Sheets schema clarity | **Non-compliant** | Headers embedded in code; schema discovery limited to overwriting row 1 rather than reading config tab; `CLANLIST_TAG_COLUMN` default to numeric constant.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L320-L356】 |
| Ops visibility | **Partial** | Watch logs stored in-memory only; optional channel ping for refresh; no persistent logging or alerting on placement failures beyond console prints.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L700-L724】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1603-L1611】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L489】 |

**Guardrail evidence snippets:**
- Env-config IDs (no constants baked in):
  ```py
  WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
  PROMO_CHANNEL_ID = int(os.getenv("PROMO_CHANNEL_ID", "0"))
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L38-L55】
- Feature flags wrapping listeners:
  ```py
  if ENABLE_LIVE_WATCH and ENABLE_LIVE_WATCH_WELCOME and _is_thread_in_parent(th, WELCOME_CHANNEL_ID):
      text = _aggregate_msg_text(message)
      if is_close_marker(text):
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1668】
- Schema hard-code example:
  ```py
  HEADERS_SHEET1 = ["ticket number","username","clantag","date closed"]
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L122】

## 7) Migration Inputs
- **Reusable assets**: Help embed copy and structure; tag picker UX (dropdown, timeout reload, text fallback); Sheets diff formatting logic for audit trails.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L191-L231】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L459】
- **Risky patterns to avoid**: Hard-coded sheet headers/tabs, direct `os._exit` reboot command, process restarts on watchdog triggers without graceful recovery, reliance on thread name parsing for placement identity.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1266-L1273】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1449-L1498】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1726-L1773】
- **Legacy strings to preserve**: `Closed-####-username-TAG` rename pattern; success confirmation "Got it — set clan tag to …"; prompt intro "Which clan tag for …"; watch status headings (`👀 **Watchers**`).【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L806-L859】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L700-L724】
- **Alignment with upcoming concepts**: No references to `CLANS_TAB=bot_info`, E/AF/AC flows, or reservations; only clanlist tab assumption and welcome/promo dichotomy.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L320-L356】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L861-L959】

**Supporting snippets:**
- Rename pattern enforcement:
  ```py
      core = f"{_fmt_ticket(ticket)}-{username}-{clantag}".strip("-")
      desired = f"Closed-{core}"
      if cur_norm != desired and clantag:
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L812-L822】
- Watchdog restart trigger:
  ```py
      await _maybe_restart(f"zombie: no events {int(idle_for)}s, latency={latency}")
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1459-L1462】
- Backfill diff text builder:
  ```py
      data = _build_backfill_details_text()
      buf = io.BytesIO(data.encode("utf-8"))
  ```
  【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1184-L1188】

## 8) Recommendations for Spec
- **Retain**
  - Thread-based close detection plus dropdown/tag text fallback to minimize recruiter friction.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1665-L1695】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L773-L804】
  - Backfill tooling that scans archived threads with diff export—valuable for data reconciliation.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L861-L919】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1186-L1204】
- **Retire/Rework**
  - Thread-name parsing as single source of truth; move to structured metadata or Forms to avoid rename drift.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1726-L1773】
  - Direct Google Sheets coupling; define abstraction that can switch to Config-driven schema and fail-soft connectors.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L121-L156】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L434-L489】
  - Process-killing `!reboot` and watchdog resets; replace with health endpoints and feature flags that degrade gracefully.【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1266-L1273】【F:AUDIT/20251010_src/WC/bot_welcomecrew.py†L1449-L1498】
- **Design questions**
  - Where should placement data live (Sheets vs. DB) and how do we define schema via config tabs to satisfy guardrails?
  - How will Welcome & Placement v2 signal required metadata (clan tag, placement outcome) without relying on thread names?
  - What observability pipeline (logs, alerts) is required for placement failures beyond ephemeral console prints?
  - Which legacy strings/embeds must be preserved to avoid recruiter confusion during transition?
