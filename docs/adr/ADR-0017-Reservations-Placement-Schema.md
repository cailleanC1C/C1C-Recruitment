# ADR-0017 — Reservations & Placement Schema
**Date:** 2025-10-25
**Phase:** 7 — Placement Tools
**Milestone:** Harmonize v1.0
**Related Epic:** Welcome & Placement v2
**Status:** obsolete

---

## 1 · Context
Legacy WelcomeCrew embedded placement data directly into Sheets and parsed thread names for clan tags.
That design lacked persistence, data validation, and failed guardrails.
Phase 7 introduces a durable reservation model tied to Config-driven tabs and validated clan tags from the **Onboarding → ClanList (column AF)** sheet.

---

## 2 · Decision
Two coordinated Sheets layers:

| Layer | Sheet | Purpose |
| --- | --- | --- |
| Operational | `CLANS_TAB` (`bot_info`) | Displays live recruiter panel data |
| Transactional | `Reservations` | Stores reservation lifecycle |

Formulae: `AF = max(0, AG − active_res)` and `AC = "N → @user1, @user2"`.
Only AF & AC are bot-written; E and AG remain manual.
All reads start at row 4 (headers = 1–3).
Every `clan_tag` must exist in **ClanList (B)**.

### Implementation Notes

Implementation Notes — Manual Fallback Trigger
A secondary manual trigger exists for environments without Ticket Tool integration. When welcome_dialog is active, a 🧭 reaction on the thread’s first message by a Recruiter, Staff, or Admin starts the same welcome dialog flow.

Phase 7 adds the automated Ticket Tool trigger (source="ticket") and the manual 🧭 reaction trigger (source="emoji").
Both call start_welcome_dialog, which performs gating, logging, and deduplication before the actual modal launches.

Shares all validation and deduplication with the automated path.

Parent channel must be a configured welcome/promo parent.

Start/skip/reject outcomes are logged in the repository’s usual structured format.

Implementation Notes — Sheet-driven Schema & Rules
- Question definitions now live in **OnboardingQuestions** with per-flow rows (`flow`, `order`, `qid`, etc.).
- Select options are parsed from the `note` column; canonical tokens (lowercase + hyphen) back the display labels for stable matching.
- Question schemas are cached per flow and surfaced via `schema_hash(flow)` in dialog start logs for traceability.
- The rules column supports `if <token> skip ...` and `if <token> make ... optional`, with `7*` syntax to target grouped orders; evaluations map to `show`/`optional`/`skip` visibility for downstream UI.

---

## 3 · Data Schema

### CLANS_TAB (`bot_info`)
| Col | Meaning | Maintained by | Notes |
| --- | --- | --- | --- |
| AF | Open spots corrected | Bot | computed |
| AG | Inactives | Manual | untouched |
| AI | Reservations display | Bot | computed |
| E | Manual open spots | Manual | base value |
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
- Epic: `docs/epic/EPIC_WelcomePlacementV2.md`
- Sheets: `Config`, `FeatureToggles`, `bot_info`, `Onboarding → ClanList (B)`, `Reservations`

---

**[meta]**
labels: docs, architecture, comp:onboarding, comp:placement, comp:data-sheets, bot:recruitment
milestone: Harmonize v1.0
**[/meta]**

Doc last updated: 2025-10-28 (v0.9.7)
