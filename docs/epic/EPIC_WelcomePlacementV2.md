# [EPIC] — Welcome & Placement v2  
**Phase:** 7 — Placement Tools  
**Milestone:** Harmonize v1.0  
**Status:** Specification (pre-implementation)  
**Related ADR:** 0014 — Reservations & Placement Schema  
**Modules affected:** onboarding, placement, recruitment, sheets services  
**Owner:** Recruitment Bot (CoreOps-aligned)

---

## 1 · Purpose  
Integrate the legacy WelcomeCrew flow with new placement tools.  
Every welcome or promo ticket thread becomes a self-contained onboarding process:  
questionnaire → recruiter review → clan placement or reservation.  
All operations are Config-driven, RBAC-checked, and log-visible.

---

## 2 · User Roles  
| Role | Abilities |
| --- | --- |
| Recruit | answers questionnaire only |
| Recruiter | may reserve, change, cancel, renew spots |
| Guardian Knight | closes threads; finalizes placements |
| Bot | handles joins, dialogs, timers, Sheet sync |

---

## 3 · Channels  
| Channel | Usage |
| --- | --- |
| `WELCOME_CHANNEL_ID` | new members |
| `PROMO_CHANNEL_ID` | external recruits |

Threads: `####-username` (Ticket Tool default).  
Bot joins automatically if parent matches either channel.

---

## 4 · Feature Toggles & Config  
All toggles live in **FeatureToggles** tab, not ENV.

| Key | Default | Description |
| --- | --- | --- |
| `placement_reservations` | false | enables reservation UI + timers |
| `welcome_dialog` | false | enables questionnaire dialogs |
| `placement_target_select` | true | legacy close-panel placement |
| (from Config tab) `CLANS_TAB` | `bot_info` | clan data tab name |

Missing Config → log channel warning + safe disable.

---

## 5 · Lifecycle

1. **Thread creation**  
   Ticket Tool opens thread → bot joins.  
   If `welcome_dialog` enabled, the bot waits for the Ticket Tool **Close-button message**, reacts 👍, and starts the welcome dialog.

2. **Questionnaire**  
   Multi-page modal (per channel).  
   On completion, bot posts **summary embed** with recruiter-only controls:  
   *Reserve Spot*, *Change*, *Cancel*.

3. **Reservation flow** (`placement_reservations`)  
   - Clan dropdown populated from **Onboarding → ClanList (column B)**.  
   - Date/time input uses the same picker logic as the Ticket Tool **Close** flow.  
   - On submit: add or update reservation row, then recompute E & AC immediately.

4. **Thread close**  
   Legacy close watcher behavior remains untouched.  
   If a reservation exists:  
   - **Same clan** → delete reservation, no count change.  
   - **Different clan** → delete reservation, free one slot.  
   Onboarding log unchanged.

5. **Reservation expiry**  
   Background loop checks timers every 15 min.  
   On expiry → mark row expired, recompute, ping `RECRUITER_ROLE_IDS` in thread with **Renew** button (opens same date modal).

6. **Refresh & restart**  
   - On boot → rebuild timers from `Reservations`.  
   - Every **3 hours** (existing cron) → batch recompute E & AC for all clans.  
   - `!rec refresh clansinfo` / `!rec refresh all` → manual trigger.  

---

## 6 · Data Model

### 6.1 CLANS_TAB (`bot_info`)  
Data starts at **row 4** (rows 1–3 = header).

| Col | Meaning | Maintained by | Notes |
| --- | --- | --- | --- |
| E | Open spots (corrected) | Bot | `E = max(0, AG − active_res)` |
| AF | Inactives | Manual | untouched |
| AC | Reservation display | Bot | `N → @user1, @user2` |
| AG | Manual open spots | Manual | source value |

**Important:** `clan_tag` values in Reservations are validated against **Onboarding → ClanList (column B)**, not CLANS_TAB.

### 6.2 Reservations tab  
| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `thread_id` | int | 125839402393 | Discord thread |
| `ticket_user_id` | int | 95830240231 | recruit |
| `recruiter_id` | int | 8392012345 | staff |
| `clan_tag` | str | C1CM | short tag from ClanList (B) |
| `clan_name` | str | Martyrs | optional display copy |
| `reserved_until` | datetime | 2025-11-03 22:00 | uses same picker as Close |
| `created_at` | datetime | 2025-10-25 17:02 | auto |
| `status` | enum | active / expired / cancelled / closed_same_clan / closed_other_clan | |
| `notes` | str | optional | comments |

---

## 7 · Bot Behaviour

| Event | Action |
| --- | --- |
| `on_thread_create` | join thread if parent ∈ {WELCOME, PROMO} |
| `on_message` | detect Ticket Tool close-button message → react 👍 → start dialog |
| `on_thread_update` | legacy close watcher (unchanged) |
| Reservation buttons | recruiter-only; manage reservation lifecycle |

**Validation:** all clan selections resolved via **ClanList (B)** before any Sheet write.

---

## 8 · Recompute Logic  
1. Build valid clan set from **ClanList (B)**.  
2. Group active reservations by `clan_tag`.  
3. For each clan:  
   - `count = len(active)`  
   - `E = max(0, AG − count)`  
   - `AC = "{count} → " + ", ".join(usernames)`  
4. Batch-update rows (row ≥ 4).  

Triggered by reservation events, 3 h cron, or manual refresh commands.

---

## 9 · Logging & Recovery  
| Event | Log Destination |
| --- | --- |
| Sheet failure | `LOG_CHANNEL_ID` embed + retry |
| Missing config/toggle | log warning |
| Reservation event | runtime line + thread note |
| Expiry | ping + Renew button |
| Invalid clan_tag | thread error + log error |
| Cron summary | info embed (counts / clans) |

---

## 10 · Compatibility
| Legacy | New handling |
| --- | --- |
| Watchers | kept, modernized |
| TagPicker UX | retained |
| Name parsing | removed |
| Backfill | kept for audit |
| Watchdog restarts | removed |
| Help embed | untouched |
| Manual headers | Config-driven reads (row 4 start) |

---

## 11 · Acceptance
1. Recruiters can reserve / cancel / renew spots.  
2. E & AC recompute automatically and via cron/commands.  
3. Reservation data survives restarts.  
4. Logging visible in log channel.  
5. RBAC enforced; help auto-lists new actions.  
6. No crash on missing config.

---

## 12 · Deliverables  
Follow existing repo layout exactly.  

- `modules/onboarding/watcher_welcome.py` — thumbs-up trigger + questionnaire start  
- `modules/onboarding/watcher_promo.py` — same logic for promo  
- `modules/placement/target_select.py` — reservation cleanup on close (legacy flow preserved)  
- `modules/placement/reservations.py` — reservation lifecycle + recompute calls  
- `modules/recruitment/views/reservation_controls.py` — recruiter buttons  
- `modules/recruitment/views/summary_embed.py` — dialog summary embed  
- `modules/recruitment/services/reservations_store.py` — Reservations tab I/O  
- `modules/recruitment/services/clans_tab.py` — CLANS_TAB recompute (row 4 offset)  
- `docs/adr/ADR-0014.md` — architecture rationale  
- Updated FeatureToggles / Config tab templates  
- Updated Command Matrix entries for RBAC  

---

**[meta]**  
labels: docs, comp:onboarding, comp:placement, comp:data-sheets, bot:recruitment  
milestone: Harmonize v1.0  
**[/meta]**

Doc last updated: 2025-10-25 (v0.9.5)
