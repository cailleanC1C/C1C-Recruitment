# Welcome Flow

## Overview
The welcome questionnaire now runs entirely inside the ticket thread. Recruits (or authorized staff) press the persistent **Open questions** button to launch an in-thread wizard, answer each question inline, and submit a single embed summary back to the thread. Open questions starts an in-thread wizard (no modal). Config key: `ONBOARDING_TAB`.

## Flow steps
1. **Panel posted** – The watcher listens for the welcome greeting phrase (`"awake by reacting with"`) or the 🎫 emoji. It reacts 👍 to the greeting and posts a fresh message with the persistent **Open questions** button.
2. **In-thread wizard** – Pressing the button posts the first onboarding question directly in the thread with navigation controls. Each answer is captured inline and retains previously provided values when the wizard is resumed.
3. **Review & Confirm** – After the final question, the wizard shows a summary in-thread with edit/submit controls so the recruit can revise any section before finalizing.
4. **Submit** – Confirming posts a single embed in the thread. The embed lists every question and answer (split across multiple embeds if Discord field limits require) and records who submitted along with a UTC timestamp.
5. **Follow-up** – Coordinators pick up directly in the thread. The session can be resumed or restarted at any time by pressing either **Open questions** or the persistent **Restart** button.

## Ticket logging & placement sync
- **Thread open → Sheet row.** When Ticket Tool creates a `W####-username…` thread, the welcome watcher parses the ticket number and username and upserts a row into the onboarding workbook (`ticket_number`, `username`, `clantag`, `date_closed`). `clantag`/`date_closed` remain blank until a recruiter closes the ticket.
- **Ticket close → Clan prompt.** When Ticket Tool posts “Ticket Closed…”, the watcher posts a dropdown + free-text prompt listing cached clan tags (including the pseudo tag `NONE`). Recruiters can pick from the menu or type a valid tag manually.
- **Confirmation → Sheet + rename.** Selecting a tag (or typing one) updates the onboarding row with the final clan tag and closure timestamp, confirms in-thread (`Got it — set clan tag to…`), and renames the thread to `Closed-####-username-TAG`.
- **Reservations & availability.** The watcher resolves any active reservation for the recruit:
  - Reservation matches final clan → status `closed_same_clan`, no manual open-spot change.
  - Reservation differs → status `closed_other_clan`; restore the reserved clan’s manual open count (+1) and consume one seat from the final clan (-1).
  - No reservation → consume one manual open spot from the final clan (-1).
  - Final tag `NONE` → reservation (if any) is cancelled, restoring the reserved clan’s manual open count (+1); no manual change for the pseudo tag.
  All adjustments call the same helpers as `!reserve`, including `adjust_manual_open_spots` and `recompute_clan_availability`, so AF/AH/AI stay in sync with the ledger.

## Triggers
- **Greeting phrase:** When a message in the welcome thread contains `"awake by reacting with"` (case-insensitive) the bot reacts 👍 and posts the panel.
- **🎫 emoji:** When the recruit, a RecruitmentCoordinator, or a GuardianKnight adds 🎫 in the welcome thread the bot posts another panel message. The watcher never edits existing panels—each trigger posts a new one to avoid stale-message errors.

### Authorization
A user may open and complete the onboarding questionnaire if they can read the welcome thread.
No target-user resolution is required. Recruiter/Admin roles are not needed to kick off or complete the flow.

### Thread-Access Gate (Phase 7)
- Every button interaction is deferred immediately to avoid “Interaction failed” toasts.
- Access is granted solely by `view_channel` in the active ticket thread. If the user cannot see the thread, the deferred response is edited with a denial notice.
- The Restart button uses the same access gate and re-triggers the full onboarding flow in place.

Always defer the interaction before posting the wizard message to avoid “Interaction failed” toasts.

## Restart rules
- Sessions survive restarts thanks to the persistent view ID. If the modal flow is already in progress, pressing the button offers a resume/restart choice. Losing in-memory state is harmless—the recruit can simply start over.

## Logging
All watcher and modal events emit structured console logs plus Discord-facing summaries in the ops channel. Examples:
```
✅ Welcome panel — actor=@Recruit • thread=#welcome › ticket-0123 • channel=#WELCOME CENTER › welcome • result=posted • details:view=panel; source=phrase
✅ Welcome panel — actor=@Guardian • thread=#welcome › ticket-0123 • channel=#WELCOME CENTER › welcome • result=posted • details:view=panel; source=emoji; emoji=🎫
⚠️ Welcome panel — actor=@Member • thread=#welcome › ticket-0123 • channel=#WELCOME CENTER › welcome • result=not_eligible • details:view=panel; source=emoji; reason=missing_role_or_owner; emoji=🎫
✅ Welcome panel — actor=@Recruit • thread=#welcome › ticket-0123 • channel=#WELCOME CENTER › welcome • result=completed • details:view=preview; questions=16; source=panel
```

Gate instrumentation surfaces as single-line console logs:
```
✅ Welcome — gate=ok • user=Guardian • channel=#welcome-center › ticket-0123 • reason=view_channel
🔐 Welcome — gate=deny • user=Recruit • channel=#welcome-center › ticket-0123 • reason=no_view_channel
⚠️ Welcome — followup fallback • action=edit_original • why=Forbidden
```

---
## Known pitfalls

- **Always defer first.** Defer the button interaction before posting or editing the wizard message; otherwise Discord returns `response_is_done: true` and the launch fails.

Doc last updated: 2025-11-14 (v0.9.7)
