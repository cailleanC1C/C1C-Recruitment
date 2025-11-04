# Onboarding Runbook

## Input method
The onboarding flow now runs on a **single rolling card** instead of multiple messages.
Each question edits the same message:

* `short`, `paragraph`, `number` → click **Enter answer**, type in thread.
* Invalid input shows a ❌ inline hint; valid answers advance automatically.
* A compact “So far” section lists answered questions as **label → value**.

For `bool` questions the card shows **Yes/No** buttons.  
For `single-select` and `multi-select-N` it shows a dropdown (with max N selections).  
Options come from the sheet (`validate: values: A, B, …` or `note`).

After the final summary is posted, the bot deletes the user's captured answer messages (only those), if cleanup is enabled.

### Testing (manual)
1. Click **Open questions** → view disables with “Launching…”.
2. First question appears on the rolling card.
3. Click **Enter answer** → card shows “Waiting for <user>…”.
4. Type a valid and invalid value.
   - Invalid → ❌ inline hint.
   - Valid → advances, updates summary.
5. After the last question, the card shows the final summary and performs cleanup (if enabled).

### Guardrails
- No modals or ephemerals.
- No new sheet columns.
- Cleanup happens after the summary card if enabled via config.
- Sheet remains the source of truth.
- No AUDIT changes.

### Startup behavior
- On bot start, the onboarding module **preloads** the questions from the sheet once.
- Logs:
  - `onb preload ok count=N sample=…` when rows load.
  - `onb preload: 0 rows…` when the tab is empty or flow filter yields none.
  - `onb preload failed …` on exceptions (startup continues).

Doc last updated: 2025-11-04 (v0.9.7)
