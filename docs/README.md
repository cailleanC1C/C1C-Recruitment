# C1C Recruitment Bot Documentation Overview (v0.9.7)

## Purpose
This index explains the intent and ownership of every file in the documentation tree.
It exists so that contributors update the correct references after each development wave or PR.

## Folder Map

### Root docs
* [`Architecture.md`](Architecture.md) — canonical runtime architecture, data flows, and environment map.
* [`README.md`](README.md) — you are here; master index for the documentation tree.
* [`Runbook.md`](Runbook.md) — canonical operator procedures (deploy, health, refresh, and maintenance cadences).
* [`Troubleshooting.md`](Troubleshooting.md) — quick reference for diagnosing common issues.

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
* [`ADR-0019 — Introduction of Clan Seat Reservations`](adr/ADR-0019-Introduction-of-Clan-SeatReservations.md) — clan seat reservation system rollout for recruiters.
* [`ADR-0020 — Availability Derivation`](adr/ADR-0020-Availability-Derivation.md) — derivation of availability states from reservation data.
* [`ADR-0021 — Availability Recompute Helper`](adr/ADR-0021-availability-recompute-helper.md) — reservations sheet adapter and recompute helper.
* [`ADR-0022 — Module Boundaries`](adr/ADR-0022-Module-Boundaries.md) — onboarding vs welcome module boundaries and update discipline.
* [`README.md`](adr/README.md) — ADR index and authoring guidelines.

### `/docs/epic/` — Feature Epics
* [`README.md`](epic/README.md) — epic index and submission expectations.
* [`EPIC_WelcomePlacementV2.md`](epic/EPIC_WelcomePlacementV2.md) — welcome & placement v2 thread-first onboarding flow.
* [`EPIC_DailyRecruiterUpdate.md`](epic/EPIC_DailyRecruiterUpdate.md) — daily recruiter update reporting pipeline.
* [`EPIC_ClanSeatReservationSystem.md`](epic/EPIC_ClanSeatReservationSystem.md) — Clan Seat Reservation System v1

### `/docs/_meta/`
* [`COMMAND_METADATA.md`](_meta/COMMAND_METADATA.md) — canonical command metadata export for Ops and diagnostics.
* [`DocStyle.md`](_meta/DocStyle.md) — single source for doc formatting plus log/embed/help UX style.

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
* [`Logging.md`](ops/Logging.md) — logging templates, dedupe policy, and configuration toggles.
* [`PermCommandQuickstart.md`](ops/PermCommandQuickstart.md) — quickstart for the `!perm bot` command surface.
* [`Watchers.md`](ops/Watchers.md) — canonical source for watchers, schedulers, watchdog thresholds, and keepalive behaviour.

### `/docs/modules/` — Module Deep Dives
* [`README.md`](modules/README.md) — module inventory with entry points and links to each deep dive.
* [`CoreOps.md`](modules/CoreOps.md) — scheduler contracts, cache façade responsibilities, and lifecycle ownership.
* [`CoreOps-Development.md`](modules/CoreOps-Development.md) — developer-focused CoreOps guidance (telemetry helpers, preload contracts).
* [`Onboarding.md`](modules/Onboarding.md) — onboarding engine scope, flows, sheet mappings, and dependencies.
* [`Welcome.md`](modules/Welcome.md) — welcome UX scope, ticket-thread flow, summary formatting, and integrations.
* [`Placement.md`](modules/Placement.md) — placement ledger, clan math reconciliation, and reservation upkeep (commands + cron jobs).
* [`Recruitment.md`](modules/Recruitment.md) — recruitment module responsibilities, sheet schemas, panels, and reporting flows.
* [`PermissionsSync.md`](modules/PermissionsSync.md) — bot access list administration and channel overwrite sync runbook.

### `/docs/reference/`
* [`Commands.md`](reference/Commands.md) — supplemental command reference for operational usage.
* [`Env.md`](reference/Env.md) — minimal environment checklist highlighting required keys and onboarding fallbacks.
* [`ModuleToggles.md`](reference/ModuleToggles.md) — module-level feature toggle reference.
* [`OnboardingConfig.md`](reference/OnboardingConfig.md) — onboarding sheet schema, cache lifecycle, and escalation notes.

### `/docs/runbooks/`
* [`Onboarding-Runbook.md`](runbooks/Onboarding-Runbook.md) — rolling-card onboarding operations and validation flow notes.
* [`WelcomePanel.md`](runbooks/WelcomePanel.md) — persistent welcome panel behaviour, recovery workflow, and operator tips.

### `/docs/specs/`
* [`WelcomeFlow.md`](specs/WelcomeFlow.md) — ticket-thread questionnaire flow and modal interaction notes.
* [`Welcome_Summary_Spec.md`](specs/Welcome_Summary_Spec.md) — summary embed layout, formatting rules, and hide logic.

## Maintenance Rules
* Update this index whenever documentation files are added, renamed, or removed.
* Any PR that modifies documentation must reflect its changes here and, if structural, call them out in the CollaborationContract.
* Ensure the version shown in this index (currently v0.9.7) matches the bot version in the root `README.md`.
* CI/linters/type-checks/tests ignore `AUDIT/`; audits write results into `AUDIT/<YYYYMMDD>_*` and add a pointer in `CHANGELOG.md`.

## Cross-References
* [`docs/contracts/CollaborationContract.md`](contracts/CollaborationContract.md) documents contributor responsibilities and embeds this index under “Documentation Discipline.”

Doc last updated: 2025-11-17 (v0.9.7)
