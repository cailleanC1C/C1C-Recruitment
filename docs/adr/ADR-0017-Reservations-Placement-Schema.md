# ADR-0017 — Reservations & Placement Schema
**Date:** 2025-10-25
**Phase:** 7 — Placement Tools
**Milestone:** Harmonize v1.0
**Related Epic:** Welcome & Placement v2
**Status:** Draft

---

## 1 · Context
Legacy WelcomeCrew embedded placement data directly into Sheets and parsed thread names for clan tags.
That design lacked persistence, data validation, and failed guardrails.
Phase 7 introduces a durable reservation model tied to Config-driven tabs and validated clan tags from the **Onboarding → ClanList (column B)** sheet.

---

## 2 · Decision
Two coordinated Sheets layers:

| Layer | Sheet | Purpose |
| --- | --- | --- |
| Operational | `CLANS_TAB` (`bot_info`) | Displays live recruiter panel data |
| Transactional | `Reservations` | Stores reservation lifecycle |

Formulae: `E = max(0, AG − active_res)` and `AC = "N → @user1, @user2"`.
Only E & AC are bot-written; AF and AG remain manual.
All reads start at row 4 (headers = 1–3).
Every `clan_tag` must exist in **ClanList (B)**.

---

## 3 · Data Schema

### CLANS_TAB (`bot_info`)
| Col | Meaning | Maintained by | Notes |
| --- | --- | --- | --- |
| E | Open spots corrected | Bot | computed |
| AF | Inactives | Manual | untouched |
| AC | Reservations display | Bot | computed |
| AG | Manual open spots | Manual | base value |
| — | — | — | **Lookup:** `clan_tag` validated via Onboarding → ClanList (B)** |

### Reservations
| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `thread_id` | int | 125839402393 | Discord thread |
| `ticket_user_id` | int | 95830240231 | recruit |
| `recruiter_id` | int | 8392012345 | staff |
| `clan_tag` | str | C1CM | Short tag only; must match Onboarding → ClanList (B) |
| `clan_name` | str | Martyrs | Optional display copy |
| `reserved_until` | datetime | 2025-11-03 22:00 | Same picker logic as Ticket Tool Close |
| `created_at` | datetime | 2025-10-25 17:02 | auto |
| `status` | enum | active / expired / cancelled / closed_same_clan / closed_other_clan | |
| `notes` | str | optional | comments |

---

## 4 · Operational Model
- Create / Change / Cancel / Renew → write or update row; recompute affected clan.
- Close → same clan = delete only; different clan = delete + free spot.
- Expire → mark expired; ping `RECRUITER_ROLE_IDS`; recompute.
- Recompute cadence → 3 h cron + manual refresh + on-event.
- Validation → clan_tag lookup against ClanList (B); invalid entries rejected and logged.

---

## 5 · Failure & Recovery
| Case | Handling |
| --- | --- |
| Write failure | log once → retry |
| Missing Config | warn → disable feature |
| Restart | rebuild timers from Reservations |
| Data drift | next recompute heals |
| Deleted thread | mark stale on next sync |

---

## 6 · Consequences
**Pros** — persistent auditable data; guardrail compliance; auto correction; panel compatibility.
**Cons** — slightly higher Sheet I/O; requires migration of manual reservations.
**Future** — closed-reservation archive or cache layer if needed.

---

## 7 · References
- Audit: `AUDIT/20251025_welcomecrew_audit/Report.md`
- Epic: `docs/epic/EPIC_WelcomePlacementV2.md`
- Sheets: `Config`, `FeatureToggles`, `bot_info`, `Onboarding → ClanList (B)`, `Reservations`

---

**[meta]**
labels: docs, architecture, comp:onboarding, comp:placement, comp:data-sheets, bot:recruitment
milestone: Harmonize v1.0
**[/meta]**

Doc last updated: 2025-10-25 (v0.9.5)
