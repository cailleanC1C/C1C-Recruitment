# Phase 3 — Dependency & Load Map (Runtime, Sheets, Watchers)

_A living reference for anyone touching the async Sheets layer, watchers, or config._

## TL;DR
- **Load order:** config → runtime → sheets core → sheets.{recruitment,onboarding} → features (commands/watchers) → Discord.
- **Data path:** features → sheets.* → shared.sheets.core → Google Sheets.
- **Reloads:** `!reload` = re-read config + clear TTL caches (+ optional handle eviction). Scheduled refresh = clear TTL caches only.
- **Toggles:** `WELCOME_ENABLED` master; `ENABLE_WELCOME_WATCHER` / `ENABLE_PROMO_WATCHER` per-watcher.
- **RBAC:** Role gates come solely from `shared.coreops_rbac` (which reads `shared.config`).

---

## 1) Boot & Load Order (must)

1. **shared.config**  
   Loads env snapshot (IDs, toggles, sheet IDs/tab names, TTLs). Single source of truth.
2. **shared.runtime**  
   Logging, scheduler, watchdog; exposes `Runtime.send_log_message`, `schedule_at_times`.
3. **shared.sheets.core**  
   Service-account client + workbook/worksheet caches (sync under the hood until Phase 3 wraps).
4. **sheets.recruitment** / **sheets.onboarding**  
   TTL caches + tab resolution (`bot_info`, `WelcomeTemplates`, `WelcomeTickets`, `PromoTickets`, `ClanList`).
5. **Feature modules**  
   - Recruitment welcome bridge (reads templates via `sheets.recruitment`).  
   - Onboarding watchers (welcome/promo) — must only call `sheets.*` helpers.
6. **Discord extensions**  
   Commands + watcher event handlers register here.

> If 1–4 fail: abort boot. If 5 fails: load minus that feature, log once to `LOG_CHANNEL_ID`.

---

## 2) Runtime Data Flows

### Reads
- Watchers need: `ClanList` (tags) and, optionally, ticket rows for dedupe checks.  
- Recruitment commands need: `bot_info` (clans) + `WelcomeTemplates`.

Path: **feature → sheets.recruitment/onboarding → shared.sheets.core → Sheets**.

### Writes
- Watchers write `WelcomeTickets` and `PromoTickets` and may call `dedupe`.  
- All writes go through `sheets.onboarding` helpers, which call `core.call_with_backoff`.

---

## 3) Caches & Invalidation Rules

- **core**: workbook/worksheet handle cache (no TTL).
- **sheets.recruitment / sheets.onboarding**: TTL caches for values (clans, templates, tags, config).
- **feature layer**: tiny in-memory bits (e.g., last 50 watch log lines).

**Invalidation**
- `!reload` (Phase 3b):  
  1) `shared.config.reload_config()`  
  2) Clear all `sheets.*` TTL caches  
  3) _Optional:_ evict `core` worksheet handles (see policy below).
- **Scheduled refresh** (3×/day): clear `sheets.*` TTL caches, then warm.
- **Write path**: surgically invalidate the affected tab cache (don’t nuke everything).

_Default TTL proposal_: `clans=15m`, `templates=15m`, `clan_tags=60m`.

---

## 4) Toggles & Role Gates

- `WELCOME_ENABLED` — master enable for welcome command and both watchers.  
- `ENABLE_WELCOME_WATCHER`, `ENABLE_PROMO_WATCHER` — register handlers + schedule loops only if true.  
- RBAC sets: `ADMIN_ROLE_IDS`, `STAFF_ROLE_IDS`, `RECRUITER_ROLE_IDS`, `LEAD_ROLE_IDS` → via `shared.coreops_rbac`.  
- `GUILD_IDS` allow-list — enforced at startup; unexpected guild later → log + exit.

---

## 5) Scheduler & Watchdog Responsibilities

- **shared.runtime** scheduler owns:  
  - Sheets refresh (invalidate → warm → log).  
  - Daily recruiter summary (via recruitment module).  
  - Any periodic hygiene tasks.
- **Watchdog**: single loop owned by runtime; modules only publish timestamps/metrics it reads.

---

## 6) Event Handler Registration Lifecycle

On watcher `setup()`:
- If toggled **off** → post one “disabled” notice to `LOG_CHANNEL_ID`, return.
- If **on** → register `on_message` + `on_thread_update` (welcome/promo), and schedule refresh jobs via Runtime.

---

## 7) Failure Containment & Health Signals

- **Read failure** → return stale cache if present; log error; handlers stay responsive.  
- **Write failure** → structured log (ticket, tab, row, reason); enqueue bounded retry task.  
- **Config/tab resolution failure** → mark watcher “degraded” (no writes), commands that don’t rely on that tab still work.  
- **Health**: `!health`, `/healthz`, and `!watch_status` (on/off + last 5 actions).  
- **Logs**: always to `LOG_CHANNEL_ID` (Phase 2 decision).

---

## 8) ASCII Dependency Diagram

