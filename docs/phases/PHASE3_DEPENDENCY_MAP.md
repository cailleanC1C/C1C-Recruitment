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

```

Discord events/commands
        │
        ▼
feature modules ─────────┐
(watchers, welcome, etc.)│
        │                │ uses
        ▼                │
sheets.recruitment / sheets.onboarding
        │
        ▼
shared.sheets.core  ◀── shared.config (IDs, TTLs, toggles)
        │
        └─> service account client (env creds)

shared.runtime  → scheduler + watchdog + logging (used by all boxes)

```

---

## 9) Reload Cascade Examples

- **Operator runs `!reload`**  
  → `shared.config.reload_config()`  
  → clear `sheets.*` TTL caches  
  → (optional) evict `core` handles  
  → next calls refetch; watchers re-read toggles on next tick.

- **Scheduled refresh tick (02:00 / 10:00 / 18:00)**  
  → clear `sheets.*` TTL caches  
  → warm via background job  
  → post short success/failure note to `LOG_CHANNEL_ID`.

- **Template edited in Google Sheets**  
  → visible after next refresh or `!reload` — no process restart.

---

## 10) Test Matrix (Smoke)

1. Boot with watchers **off** → single “disabled” notice; no handlers registered.  
2. Boot with watchers **on**, missing template tab → welcome command surfaces actionable error; watchers still run.  
3. Simulate slow Sheets → handlers remain responsive (async `to_thread` paths).  
4. Write path: upsert welcome → read back (tab cache invalidated surgically).  
5. Dedupe path: create duplicates → run dedupe → older rows removed → only affected tab cache cleared.  
6. Allow-list: connect to unexpected guild → logged + process exits cleanly.

---

## 11) Open Configuration Edges (to decide)

- **Handle eviction on `!reload`**: keep worksheet handles (faster) vs. evict (safer against tab renames).  
  _Recommend_: keep by default; add `--deep` option to evict.
- **TTL defaults**: confirm `clans=15m`, `templates=15m`, `clan_tags=60m`.  
- **Log routing**: all diagnostics to `LOG_CHANNEL_ID` only (no public channels).

---

## 12) Related Docs

- `PHASE3_DISCOVERY.md` — source analysis and risks.  
- `PHASE3_WATCHERS_MAP.md` — attachment points and role/toggle mapping.  
- `PHASE3_CONFIG_SURVEY.md` — env + config contract.  
- `OVERVIEW_2025-10-14.md` — legacy vs live side-by-side.  

---

### Appendix: Terminology

- **TTL cache**: time-bound value cache inside `sheets.*`.  
- **Handle cache**: workbook/worksheet objects cached by `shared.sheets.core`.  
- **Surgical invalidation**: drop only the relevant tab’s cache after writes/dedupe.

