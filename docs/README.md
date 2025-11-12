# C1C Recruitment Bot Documentation Overview (v0.9.7)

## Purpose
This index explains the intent and ownership of every file in the documentation tree.
It exists so that contributors update the correct references after each development wave or PR.

## Folder Map

### Root docs
* [`Architecture.md`](Architecture.md) — high-level architecture overview and runtime map.
* [`README.md`](README.md) — you are here; master index for the documentation tree.

### `/docs/adr/` — Architectural Decision Records
* [`ADR-0000`](adr/ADR-0000-template.md) — template for proposing new architecture decisions.
* [`ADR-0001`](adr/ADR-0001-sheets-access-layer.md) — Sheets access layer contract.
* [`ADR-0002`](adr/ADR-0002-cache-telemetry-wrapper.md) — cache telemetry wrapper.
* [`ADR-0003`](adr/ADR-0003-coreops-command-contract.md) — CoreOps command contract.
* [`ADR-0004`](adr/ADR-0004-help-system-short-vs-detailed.md) — help system short vs detailed output.
* [`ADR-0005`](adr/ADR-0005-reload-vs-refresh.md) — reload vs refresh behaviour.
* [`ADR-0006`](adr/ADR-0006-startup-preloader-bot-info-cron.md) — startup preloader bot info cron.
* [`ADR-0007`](adr/ADR-0007-feature-toggles-recruitment-module-boundaries.md) — feature toggles and module boundaries.
* [`ADR-0008`](adr/ADR-0008-emoji-pipeline-port.md) — emoji pipeline port.
* [`ADR-0009`](adr/ADR-0009-recruiter-panel-text-only.md) — recruiter panel text-only workflow.
* [`ADR-0010`](adr/ADR-0010-clan-profile-with-emoji.md) — clan profile emoji policy.
* [`ADR-0011`](adr/ADR-0011-Normalize-to-Modules-First.md) — member search indexing.
* [`ADR-0012`](adr/ADR-0012-coreops-package.md) — CoreOps package structure.
* [`ADR-0013`](adr/ADR-0013-config-io-hardening.md) — config & I/O hardening (log channel, emoji proxy, recruiter Sheets, readiness route).
* [`ADR-0014`](adr/ADR-0014-async-sheets-facade.md) — async Sheets facade contract.
* [`ADR-0015`](adr/ADR-0015-config-hygiene-and-secrets.md) — config hygiene & secrets governance.
* [`ADR-0016`](adr/ADR-0016-import-side-effects.md) — import-time side effects removal.
* [`ADR-0017`](adr/ADR-0017-Reservations-Placement-Schema.md) — reservations & placement schema.
* [`ADR-0018`](adr/ADR-0018_DailyRecruiterUpdate.md) — daily recruiter update schedule and sheet-driven report.
* [`README.md`](adr/README.md) — ADR index and authoring guidelines.

### `/docs/epic/` — Feature Epics
* [`README.md`](epic/README.md) — epic index and submission expectations.
* [`EPIC_WelcomePlacementV2.md`](epic/EPIC_WelcomePlacementV2.md) — welcome & placement v2 thread-first onboarding flow.
* [`EPIC_DailyRecruiterUpdate.md`](epic/EPIC_DailyRecruiterUpdate.md) — daily recruiter update reporting pipeline.

### `/docs/_meta/`
* [`COMMAND_METADATA.md`](_meta/COMMAND_METADATA.md) — canonical command metadata export for Ops and diagnostics.
* [`DocStyle.md`](_meta/DocStyle.md) — documentation formatting conventions.

### `/docs/guardrails/`
* [`README.md`](guardrails/README.md) — high-level summary of CI-enforced guardrails surfaced on pull requests.
* [`RepositoryGuardrails.md`](guardrails/RepositoryGuardrails.md) — canonical guardrails specification covering structure, coding, documentation, and governance rules.

### `/docs/compliance/`
* [`REPORT_GUARDRAILS.md`](compliance/REPORT_GUARDRAILS.md) — guardrail compliance report template and severity mapping.

### `/docs/contracts/`
* [`core_infra.md`](contracts/core_infra.md) — runtime, Sheets access, and cache relationships.
* [`CollaborationContract.md`](contracts/CollaborationContract.md) — contributor standards, PR review flow, and Codex formatting instructions.

### `/docs/ops/` — Operational Documentation
* [`CommandMatrix.md`](ops/CommandMatrix.md) — user/admin command catalogue with permissions, feature gates, and descriptions.
* [`Config.md`](ops/Config.md) — environment variables, Config tab mapping, and Sheets schema (including `FEATURE_TOGGLES_TAB`).
* [`env.md`](ops/env.md) — minimal environment checklist highlighting required keys and onboarding fallbacks.
* [`keepalive.md`](ops/keepalive.md) — watchdog expectations, heartbeat tuning, and stall recovery notes.
* [`Logging.md`](ops/Logging.md) — logging templates, dedupe policy, and configuration toggles.
* [`module-toggles.md`](ops/module-toggles.md) — module-level feature toggle reference.
* [`Onboarding.md`](ops/Onboarding.md) — onboarding sheet schema, cache lifecycle, and escalation playbook.
* [`Onboarding-Runbook.md`](ops/Onboarding-Runbook.md) — rolling-card onboarding operations and validation flow notes.
* [`PermCommandQuickstart.md`](ops/PermCommandQuickstart.md) — quickstart for the `!perm bot` command surface.
* [`PermissionsSync.md`](ops/PermissionsSync.md) — bot access list administration and channel overwrite sync runbook.
* [`RecruiterPanel.md`](ops/RecruiterPanel.md) — interaction model for the recruiter panel UI and messaging cadence.
* [`Runbook.md`](ops/Runbook.md) — operator actions for routine tasks and incident handling.
* [`Troubleshooting.md`](ops/Troubleshooting.md) — quick reference for diagnosing common issues.
* [`Watchers.md`](ops/Watchers.md) — environment-gated welcome/promo listeners and cache refresh scheduler notes.
* [`Welcome.md`](ops/Welcome.md) — persistent welcome panel behaviour, recovery workflow, and operator tips.
* [`WelcomeFlow.md`](ops/WelcomeFlow.md) — ticket-thread questionnaire flow and modal interaction notes.
* [`Welcome_Summary_Spec.md`](ops/Welcome_Summary_Spec.md) — summary embed layout, formatting rules, and hide logic.
* [`commands.md`](ops/commands.md) — supplemental command reference for operational usage.
* [`development.md`](ops/development.md) — developer setup notes and contribution workflow guidance.

## Maintenance Rules
* Update this index whenever documentation files are added, renamed, or removed.
* Any PR that modifies documentation must reflect its changes here and, if structural, call them out in the CollaborationContract.
* Ensure the version shown in this index (currently v0.9.7) matches the bot version in the root `README.md`.
* CI/linters/type-checks/tests ignore `AUDIT/`; audits write results into `AUDIT/<YYYYMMDD>_*` and add a pointer in `CHANGELOG.md`.

## Cross-References
* [`docs/contracts/CollaborationContract.md`](contracts/CollaborationContract.md) documents contributor responsibilities and embeds this index under “Documentation Discipline.”

Doc last updated: 2025-11-12 (v0.9.7)
