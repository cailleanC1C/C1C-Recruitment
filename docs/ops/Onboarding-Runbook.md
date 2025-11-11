# Onboarding Runbook

## Input method
The onboarding flow runs as an in-thread wizard message. Each question updates the same message with inline controls:

* `short`, `paragraph`, `number` → click **Enter answer**, type in thread.
* Invalid input shows a ❌ inline hint; valid answers advance automatically.
* A compact “So far” section lists answered questions as **label → value**.

For `bool` questions the wizard shows **Yes/No** buttons.
For `single-select` and `multi-select-N` it shows a dropdown (with max N selections).
Options come from the sheet (`validate: values: A, B, …` or `note`).

After the final summary is posted, the bot deletes the user's captured answer messages (only those), if cleanup is enabled.

### Testing (manual)
1. Click **Open questions** → view disables with “Launching…”.
2. First question appears on the wizard card.
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

### Ops commands
`!ops onb reload` — reload questions from the sheet and print how many rows were found (plus sample qids).

`!ops onb check` — validate the tab, headers, and required columns.

Doc last updated: 2025-11-05 (v0.9.7)
