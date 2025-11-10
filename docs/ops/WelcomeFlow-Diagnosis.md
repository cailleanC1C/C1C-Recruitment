# Welcome Flow Diagnosis (2025-???)

## Summary
- Documenting mismatches between current documentation and implementation for welcome onboarding flow.

## Documentation expectations
- `docs/ops/WelcomeFlow.md` describes an inline, in-thread wizard triggered by **Open questions** with navigation controls and edit/submit stage (no modals).【F:docs/ops/WelcomeFlow.md†L1-L17】
- `docs/ops/Onboarding.md` and `docs/ops/Onboarding-Runbook.md` specify sheet-driven buttons for answering/skip/back, dropdowns for select questions, and a Finish step that posts a comprehensive summary embed in the thread.【F:docs/ops/Onboarding.md†L34-L105】【F:docs/ops/Onboarding-Runbook.md†L3-L24】

## Findings in the current implementation

### 1. Panel launch path still expects the deprecated rolling-card prototype
- `OpenQuestionsPanelView._handle_launch` only proceeds when the controller exposes `start_session_from_button`. Otherwise the function exits after disabling the button, leaving the UI in an error state. There is no fallback to the documented inline wizard.【F:modules/onboarding/ui/panels.py†L784-L859】
- `WelcomeController` no longer defines `start_session_from_button`, so the branch never runs. The first **Open questions** click therefore ends with the error notice and no wizard, matching the field report.【F:modules/onboarding/controllers/welcome_controller.py†L2444-L2471】

### 2. Inline wizard scaffolding is a stub and cannot collect answers
- The controller’s inline helpers currently return hard-coded placeholder questions and never write user input; `capture_step` is a no-op. The wizard therefore advances through empty prompts without ever asking for or storing values, so no dropdowns or modals appear and navigation buttons do nothing meaningful.【F:modules/onboarding/controllers/welcome_controller.py†L830-L858】
- Because nothing updates `answers_by_thread`, the OnboardWizard view cannot reflect progress, and resume/validation rules are bypassed. This contradicts the docs’ requirement for sheet-driven prompts and validation.【F:docs/ops/Onboarding.md†L34-L72】

### 3. Summary output is an unfinished stub
- `finish_and_summarize` posts a generic “New Onboarding” embed with only IGN, vibe, and timezone fields pulled from the placeholder answers, not the sheet-driven summary described in the docs.【F:modules/onboarding/controllers/welcome_controller.py†L864-L903】
- With no stored answers the embed is effectively empty, which explains the blank summary card seen by users.【F:modules/onboarding/controllers/welcome_controller.py†L883-L887】

### 4. Restart/diagnostic paths still invoke the legacy modal flow
- Because the inline controller never stores answers, restart handling immediately calls back into `start_welcome_dialog`, which rebuilds the legacy modal-based flow instead of the inline wizard.【F:modules/onboarding/ui/panels.py†L861-L885】【F:modules/onboarding/welcome_flow.py†L18-L102】
- The legacy controller logs only high-level start/finish events, so ops never receives the per-question instrumentation described in the docs while the inline stack is inactive.【F:modules/onboarding/welcome_flow.py†L68-L102】

## Root cause
The repository still contains the transitional “rolling card” prototype and placeholder inline controller. The production docs describe the completed inline wizard, but the code never finished the migration: button launch still targets the prototype, and the inline controller is stubbed out. Until the controller is fully wired to sheet-backed questions (and exposes the documented inline answer handlers), the welcome flow cannot operate as written.

