# EPIC — Daily Recruiter Update (Reporting v1)

## 0) Purpose
Define, end-to-end, the **Daily Recruiter Update** feature: one scheduled post and one manual command that read from existing recruitment caches and publish a concise daily status to a configured destination. This EPIC is the single source of truth for scope, UX, config, RBAC, failure modes, testing, rollout, and documentation. No coding until this EPIC is approved.

---

## 1) Goal & Non-Goals
**Goal**
- A minimal, reliable **Daily Recruiter Update** that:
  - runs on a schedule (cron-like time) and via an admin-gated manual command,
  - reads **existing caches** only (no extra refreshers, no direct sheet reads),
  - posts to a configured channel/thread,
  - is **fully toggle-controlled** and fails soft with useful diagnostics.

**Non-Goals (v1)**
- No new cache warmers or sheet pulls.
- No TXT attachments/export (moved to a later phase; currently out of scope).
- No new metrics beyond what caches already surface.
- No retry/backoff framework; v1 logs and exits cleanly (see v2 ideas).

---

## 2) Terminology & Sources
- **Recruitment caches**: the same cache/adapter layer used by `!clanmatch`/`!clansearch` panels (open spots, inactives, reserved, bracket rollups, etc.).
- **Destination**: Discord channel **or** thread ID for the report post.
- **CoreOps**: existing health/reload/env-status + logging; we extend its surfaces to display our new envs and help texts.

---

## 3) Dependencies
- Bot boot lifecycle (tasks start/stop hooks already present in codebase).
- **CoreOps**: we rely on existing health/reload/env-status and logging helpers; and we will **extend CoreOps surfaces** to expose the new ENV and docs (see §16 Docs & Changelog).
- **Timezone:** **Always UTC**. No local conversions anywhere.
- Sheets **Config** tab for `REPORTS_TAB` name (like other tabs).

---

## 4) Feature Toggle
- Key: `recruitment_reports` (boolean; default **false**).
- Behavior:
  - When **off**: scheduler **not** started; manual command logs an info line to the log channel that the feature is disabled.
  - When **on**: scheduler may start **only** if destination is configured; otherwise log a clear boot warning and keep scheduler disabled.

---

## 5) RBAC
- Manual command **admin-gated** via existing CoreOps role checks (same gate used for other staff/ops commands).
- Scheduler has no RBAC at runtime (it posts unprompted), but it respects the feature flag and destination config.

---

## 6) Config (ENV)
Feature is off by default.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `REPORT_RECRUITERS_DEST_ID` | str | — | Required when feature ON. Discord channel **or** thread ID. |
| `REPORT_DAILY_POST_TIME` | `HH:MM` (UTC) | `09:30` | Daily post time in **UTC**. No local conversion.

Other inputs:
- `LOG_CHANNEL_ID` — reuse the global log channel.
- `REPORTS_TAB` — provided by the **Config** sheet (not an env var). Default value there is `Statistics`.

**Validation at boot**
- If `recruitment_reports=true` and `REPORT_RECRUITERS_DEST_ID` missing → log warning: `"[report] disabled • reason=dest-missing"`. No crash.

---

## 7) Triggers
### 7.1 Scheduled
- A single daily post at `REPORT_DAILY_POST_TIME` (**UTC**). Implement via `discord.ext.tasks.loop(time=[utc_time])`.
- Idempotence: the loop only posts once per day; relies on library scheduling.

### 7.2 Manual
- Command: `!report recruiters` (admin-gated).
- Behavior: performs the same rendering + posting as the scheduler.
- **Logging, not chat reply:** on success, post a one-line entry to `LOG_CHANNEL_ID` (see §12). Only errors reply in-channel with an actionable message.

---

## 8) Data Model & Rendering Inputs
Primary source: **Reports sheet tab** defined by `REPORTS_TAB` (default `Statistics`, from the Config sheet). No direct panel queries in v1; the sheet is assumed to be populated upstream.

- Expected header row (row 1): `H1_Headline`, `H2_Headline`, `Key`, `open spots`, `inactives`, `reserved spots` (case-insensitive; trim spaces/underscores).
- Sections:
  - **General Overview**: find the row where column A equals `General Overview` (case-insensitive). Collect subsequent rows **until** a row where column A equals `Per Bracket`.
  - **Per Bracket**: starting at the row where column A equals `Per Bracket`, scan column **B** for sub-headers:
    - `Elite End Game`, `Early End Game`, `Late Game`, `Mid Game`, `Early Game`, `Beginners` (case-insensitive).
    - For each sub-header, collect the contiguous data rows **below it** until the next sub-header or blank line.
- For every data row, read columns by header mapping (not fixed positions):
  - `Key` → label printed after the bullet.
  - `open spots`, `inactives`, `reserved spots` → integer values; treat missing/blank as 0.
- **Render rule:** only output a bullet line if **at least one** of `open spots`, `inactives`, or `reserved spots` is **> 0** (to avoid clutter).
- Output line format: `🔹 **{Key}:** open {open} | inactives {inactives} | reserved {reserved}`.

- We **always** render the **Top 10** and **Top 5** lines if present in the General Overview block.

---

## 9) Output UX (v1)
Mirror our production style (like `!env`).

**Message body (above embed)**
- Use Discord header markdown: `# Update {YYYY-MM-DD}`.
- Role mentions from `RECRUITER_ROLE_IDS` (comma/space separated list handled by existing role-mention util), one per line below the header.

**Embeds**
- Embed 1: `Summary Open Spots`
  - Section 1: **General Overview** (from sheet’s *General Overview* block)
  - Section 2: **Per Bracket** with sub-sections in this order:
    - `Elite End Game`, `Early End Game`, `Late Game`, `Mid Game`, `Early Game`, `Beginners`
  - Each bullet uses the bolded blue-diamond format specified in §8.
- Embed 2: `Bracket Details`
  - One sub-section per bracket (ordered as above), with clan-level bullet lines using the same bolded label format.

**Footer**
- Include: `last updated {sheet_timestamp_utc}` and a note that this is a daily UTC snapshot on the **Summary** embed.

**Branding**
- Same embed header/footer chrome/colors as `!env`.

---

## 10) Posting & Routing
- Resolve destination from `REPORT_RECRUITERS_DEST_ID` as channel or thread.
- On send failure: print a concise line to stdout and also log a failure line to `LOG_CHANNEL_ID`.
- Manual command does **not** send a success reply to the invoking channel; success is only logged to the log channel. Errors produce an in-channel message.

---

## 11) Failure Modes & Messages
- **Feature disabled**: manual command → logs: `[report] blocked • reason=feature-off` and replies to invoker with `Daily Recruiter Update is disabled.`
- **Destination missing** (feature ON): boot log warning `[report] disabled • reason=dest-missing`; manual command reply: `Destination not configured. Set REPORT_RECRUITERS_DEST_ID.`
- **Destination not found**: reply `Could not fetch the configured destination. Check the ID and my permissions.` and log `[report] failed • reason=dest-not-found`.
- **Sheet missing/empty**: Post minimal embed with zeros and footer `last updated: —`; log `[report] posted • result=ok • note=empty-sheet`.

---

## 12) Observability
Respect our existing logging format.

Sample lines:
- Scheduler success: `[report] recruiters • actor=scheduled guild=<id> dest=<id> date=YYYY-MM-DD result=ok error=-`
- Manual success: `[report] recruiters • actor=manual user=<id> guild=<id> dest=<id> date=YYYY-MM-DD result=ok error=-`
- Failure: `[report] recruiters • actor=scheduled guild=<id> dest=<id> date=YYYY-MM-DD result=fail error=<Type>:<msg>`

All success/failure lines go to `LOG_CHANNEL_ID` (and stdout). No extra debug spam.

---

## 13) Performance & Rate Limits
- Single message per day plus optional manual invocations.
- No retries in v1; rely on manual command if a post must be re-sent.

---

## 14) Security
- Manual command is admin-gated (existing CoreOps RBAC).
- Mentions only of configured roles; no arbitrary user pings.

---

## 15) Rollout Plan
1) Ship behind toggle OFF.
2) Configure `REPORT_RECRUITERS_DEST_ID` in test → enable flag → validate manual command → validate scheduler at next window.
3) Enable in production once validated.

---

## 16) Docs & Changelog
- **README (user-facing)**: add a short “Daily Recruiter Update” capability line; mention `!report recruiters` (staff only).
- **docs/ops/CommandMatrix.md**: list `!report recruiters` with RBAC note.
- **docs/config.md**: add ENV key `REPORT_RECRUITERS_DEST_ID` and `REPORT_DAILY_POST_TIME` (UTC); explain `REPORTS_TAB` comes from the Config sheet.
- **CoreOps surfaces**:
  - `!env` must show **all** new envs (incl. `REPORT_DAILY_POST_TIME`), grouped appropriately.
  - `!checksheet` must be aware of **REPORTS_TAB** (from Config) and include it in checks.
  - `!help` must include the new `!report recruiters` command with a short help text.
- **ADR**: `ADR-0018 — Daily Recruiter Update v1` (UTC-only; sheet-driven; log-first success reporting).
- **CHANGELOG**: Version bump entry referencing Phase 6.

---

## 17) Testing & Acceptance
**Unit**
- Formatter returns expected strings given synthetic sheet payloads (fresh vs empty; missing Top lists; missing brackets).
- Time parsing uses `REPORT_DAILY_POST_TIME` (UTC).
- Command returns helpful errors for: feature OFF, dest missing, dest invalid.

**Integration (manual)**
- End-to-end post in a sandbox channel: verify header, mentions, sections, diamond bullets, and footer.

**Acceptance Criteria**
- Toggle OFF → no scheduler, command blocked with clear message.
- Toggle ON + dest set → scheduled post appears at the configured UTC time.
- Manual command works and routes to the same destination.
- No crashes; failures are logged and mirrored to the log channel.

---

## 18) Risks & Mitigations
- **Sheet shape drift**: rely on header-name mapping; missing headers become zeros and are logged.
- **Misconfigured destination**: block scheduler start at boot; helpful manual error.
- **Time drift**: daily time is read at boot; changes require restart.

---

## 19) Decisions (from Open Questions)
- **Top 10 / Top 5**: **Always** render (if present in the General Overview block).
- **Footer content**: **Yes** — show cache timestamp (`last updated …`) and “daily UTC snapshot” note.
- **Role mentions**: Use `RECRUITER_ROLE_IDS` only.

---

## 20) Future Work (Next Steps)
None planned. TXT export/logging extras are out of scope.

Doc last updated: 2025-11-23 (v0.9.8.2)
