# Welcome Flow

## Overview
The welcome questionnaire now runs entirely inside the ticket thread. Recruits (or authorized staff) press a persistent **Open questions** button to launch a paged modal flow, review their answers, and submit a single embed summary back to the thread.

## Flow steps
1. **Panel posted** – The watcher listens for the welcome greeting phrase (`"awake by reacting with"`) or the 🎫 emoji. It reacts 👍 to the greeting and posts a fresh message with the persistent **Open questions** button.
2. **Paged modals** – Pressing the button opens the onboarding questions in order. The modal pages are populated from the recruitment sheet and retain any answers already provided.
3. **Review & Confirm** – After the final page, the bot shows an ephemeral summary view with edit/submit buttons so the recruit can revise any section before finalizing.
4. **Submit** – Confirming posts a single embed in the thread. The embed lists every question and answer (split across multiple embeds if Discord field limits require) and records who submitted along with a UTC timestamp.
5. **Follow-up** – Coordinators pick up directly in the thread. The session can be resumed or restarted at any time by pressing either **Open questions** or the persistent **Restart** button.

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

Buttons that open modals must respond with the modal itself, not with a deferral.

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

- **Don't pre-respond before a modal.** `send_modal` must be the first response on the interaction; any prior defer/send forces Discord to reject the modal with `response_is_done: true`.

Doc last updated: 2025-11-02 (v0.9.7)
