# Onboarding Runbook

## Input method
The onboarding flow now runs on a **single rolling card** instead of multiple messages.
Each question edits the same message:

* `short`, `paragraph`, `number` → click **Enter answer**, type in thread.
* Invalid input shows a ❌ inline hint; valid answers advance automatically.
* A compact “So far” section lists answered questions as **label → value**.

Dropdowns, buttons, and cleanup arrive in the next update.

Doc last updated: 2025-11-03 (v0.9.7)

### Testing (manual)
1. Click **Open questions** → view disables with “Launching…”.
2. First question appears on the rolling card.
3. Click **Enter answer** → card shows “Waiting for <user>…”.
4. Type a valid and invalid value.
   - Invalid → ❌ inline hint.
   - Valid → advances, updates summary.
5. After the last question, the card shows the final summary (no cleanup yet).

### Guardrails
- No modals or ephemerals.
- No new sheet columns.
- No cleanup yet.
- Sheet remains the source of truth.
- No AUDIT changes.
