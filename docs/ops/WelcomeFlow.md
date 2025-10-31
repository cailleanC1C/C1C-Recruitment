# Welcome Flow

## Overview
The welcome questionnaire now runs entirely inside the ticket thread. Recruits (or authorized staff) press a persistent **Open questions** button to launch a paged modal flow, review their answers, and submit a single embed summary back to the thread.

## Flow steps
1. **Panel posted** – The watcher listens for the welcome greeting phrase (`"awake by reacting with"`) or the 🎫 emoji. It reacts 👍 to the greeting and posts a fresh message with the persistent **Open questions** button.
2. **Paged modals** – Pressing the button opens the onboarding questions in order. The modal pages are populated from the recruitment sheet and retain any answers already provided.
3. **Review & Confirm** – After the final page, the bot shows an ephemeral summary view with edit/submit buttons so the recruit can revise any section before finalizing.
4. **Submit** – Confirming posts a single embed in the thread. The embed lists every question and answer (split across multiple embeds if Discord field limits require) and records who submitted along with a UTC timestamp.
5. **Follow-up** – Coordinators pick up directly in the thread. The session can be resumed or restarted at any time by pressing the button again.

## Triggers
- **Greeting phrase:** When a message in the welcome thread contains `"awake by reacting with"` (case-insensitive) the bot reacts 👍 and posts the panel.
- **🎫 emoji:** When the recruit, a RecruitmentCoordinator, or a GuardianKnight adds 🎫 in the welcome thread the bot posts another panel message. The watcher never edits existing panels—each trigger posts a new one to avoid stale-message errors.

## Eligibility
- **Recruit:** The thread owner can always launch or resume the modal flow.
- **Staff:** Members with RecruitmentCoordinator or GuardianKnight roles can start the flow on behalf of the recruit.
- **Others:** Everyone else receives an ephemeral notice that the panel is restricted, and the watcher logs the blocked attempt.

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

---
Doc last updated: 2025-10-31 (v0.9.7)
