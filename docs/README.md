# C1C Recruitment Bot Documentation Overview (v0.9.6)

## Purpose
This index explains the intent and ownership of every file in the documentation tree.
It exists so that contributors update the correct references after each development phase or PR.

## Folder Map

### `/docs/adr/` — Architectural Decision Records
* Each ADR (`ADR-XXXX`) captures an approved architectural or systemic decision.
* [`ADR-0000`](adr/ADR-0000-template.md) serves as the template for new records.
* [`ADR-0001`](adr/ADR-0001-sheets-access-layer.md) — Sheets access layer contract.
* [`ADR-0002`](adr/ADR-0002-cache-telemetry-wrapper.md) — Cache telemetry wrapper.
* [`ADR-0003`](adr/ADR-0003-coreops-command-contract.md) — CoreOps command contract.
* [`ADR-0004`](adr/ADR-0004-help-system-short-vs-detailed.md) — Help system short vs detailed output.
* [`ADR-0005`](adr/ADR-0005-reload-vs-refresh.md) — Reload vs refresh behaviour.
* [`ADR-0006`](adr/ADR-0006-startup-preloader-bot-info-cron.md) — Startup preloader bot info cron.
* [`ADR-0007`](adr/ADR-0007-feature-toggles-recruitment-module-boundaries.md) — Feature toggles and module boundaries.
* [`ADR-0008`](adr/ADR-0008-emoji-pipeline-port.md) — Emoji pipeline port.
* [`ADR-0009`](adr/ADR-0009-recruiter-panel-text-only.md) — Recruiter panel text-only.
* [`ADR-0010`](adr/ADR-0010-clan-profile-with-emoji.md) — Clan profile emoji policy.
* [`ADR-0011`](adr/ADR-0011-Normalize-to-Modules-First.md) — Member search indexing.
* [`ADR-0012`](adr/ADR-0012-coreops-package.md) — CoreOps package structure.
* [`ADR-0013`](adr/ADR-0013-config-io-hardening.md) — Config & I/O hardening (log channel, emoji proxy, recruiter Sheets, readiness route).
* [`ADR-0014`](adr/ADR-0014-async-sheets-facade.md) — Async Sheets facade contract.
* [`ADR-0015`](adr/ADR-0015-config-hygiene-and-secrets.md) — Config hygiene & secrets governance.
* [`ADR-0016`](adr/ADR-0016-import-side-effects.md) — Import-time side effects removal.
* [`ADR-0017`](adr/ADR-0017-Reservations-Placement-Schema.md) — Reservations & placement schema.
* [`ADR-0018`](adr/ADR-0018_DailyRecruiterUpdate.md) — Daily recruiter update v1 (UTC schedule, sheet-driven report).
* [`ADR README`](adr/README.md) — Index for Architectural Decision Records.
* File a new ADR for every major design or structural change.

### `/docs/epic/` — Feature Epics
* Stores phase-level epic specifications ready for CoreOps implementation.
* [`EPIC_WelcomePlacementV2.md`](epic/EPIC_WelcomePlacementV2.md) — Welcome & Placement v2 thread-first onboarding flow.
* [`EPIC_DailyRecruiterUpdate.md`](epic/EPIC_DailyRecruiterUpdate.md) — Daily recruiter update reporting pipeline.
* [`Epic README`](epic/README.md) — Index for feature epic specifications.

### `/docs/compliance/`
* Houses internal compliance and governance policies.
* Example: [`REPORT_GUARDRAILS.md`](compliance/REPORT_GUARDRAILS.md) details report formatting and safety guardrail standards.

### `/docs/_meta/`
* [`DocStyle.md`](_meta/DocStyle.md) — documentation formatting conventions.

### `/docs/guardrails/`
* [`guardrails.md`](guardrails.md) — high-level summary of CI-enforced guardrails surfaced on pull requests.
* [`RepositoryGuardrails.md`](guardrails/RepositoryGuardrails.md) — canonical guardrails specification covering structure, coding, documentation, and governance rules.

### `/docs/contracts/`
* Defines long-term, structural interfaces between components.
* [`core_infra.md`](contracts/core_infra.md) documents runtime, Sheets access, and cache relationships.
* [`CollaborationContract.md`](contracts/CollaborationContract.md) — contributor standards, PR review flow, and Codex formatting instructions.

### `/docs/ops/` — Operational Documentation
* [`Architecture.md`](ops/Architecture.md) — detailed system flow, runtime design, and module topology.
* [`Config.md`](ops/Config.md) — environment variables, Config tab mapping, and Sheets schema (including `FEATURE_TOGGLES_TAB`).
* [`CommandMatrix.md`](ops/CommandMatrix.md) — user/admin command catalogue with permissions, feature gates, and descriptions.
* [`PermCommandQuickstart.md`](ops/PermCommandQuickstart.md) — quickstart for the `!perm bot` command surface.
* [`PermissionsSync.md`](ops/PermissionsSync.md) — bot access list administration and channel overwrite sync runbook.
* [`RecruiterPanel.md`](ops/RecruiterPanel.md) — interaction model for the recruiter panel UI and messaging cadence.
* [`Runbook.md`](ops/Runbook.md) — operator actions for routine tasks and incident handling.
* [`Troubleshooting.md`](ops/Troubleshooting.md) — quick reference for diagnosing common issues.
* [`Watchers.md`](ops/Watchers.md) — environment-gated welcome/promo listeners and cache refresh scheduler notes.
* [`development.md`](ops/development.md) — developer setup notes and contribution workflow guidance.
* [`commands.md`](ops/commands.md) — supplemental command reference for operational usage.
* [`module-toggles.md`](ops/module-toggles.md) — module-level feature toggle reference.

## Code Map

* `packages/c1c-coreops/` — canonical CoreOps implementation (`c1c_coreops.*`).
  Legacy shared CoreOps modules have been removed; import directly from `c1c_coreops`.

### Root-Level Docs
* [`Architecture.md`](Architecture.md) — high-level architecture overview and runtime map.
* [`README.md`](../README.md) — user-facing overview, installation steps, and configuration guidance for the bot.
* [`CHANGELOG.md`](../CHANGELOG.md) — version history for the project.

## Maintenance Rules
* Update this index whenever documentation files are added, renamed, or removed.
* Any PR that modifies documentation must reflect its changes here and, if structural, call them out in the CollaborationContract.
* Ensure the version shown in this index (currently v0.9.6) matches the bot version in the root `README.md`.

## Cross-References
* [`docs/contracts/CollaborationContract.md`](contracts/CollaborationContract.md) documents contributor responsibilities and embeds this index under “Documentation Discipline.”

Doc last updated: 2025-10-27 (v0.9.6)
