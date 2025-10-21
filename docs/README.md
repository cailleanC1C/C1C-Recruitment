# C1C Recruitment Bot Documentation Overview (v0.9.5)

## Purpose
This index explains the intent and ownership of every file in the documentation tree.
It exists so that contributors update the correct references after each development phase or PR.

## Folder Map

### `/docs/adr/` — Architectural Decision Records
* Each ADR (`ADR-XXXX`) captures an approved architectural or systemic decision.
* `ADR-0000` serves as the template for new records.
* File a new ADR for every major design or structural change.

### `/docs/compliance/`
* Houses internal compliance and governance policies.
* Example: `REPORT_GUARDRAILS.md` details report formatting and safety guardrail standards.

### `/docs/contracts/`
* Defines long-term, structural interfaces between components.
* `core_infra.md` documents runtime, Sheets access, and cache relationships.
* Feature toggle guidance moved into other docs; keep legacy references aligned if `feature_toggles.md` is touched.

### `/docs/ops/` — Operational Documentation
* `Architecture.md` — detailed system flow, runtime design, and module topology.
* `Config.md` — environment variables, Config tab mapping, and Sheets schema (including `FEATURE_TOGGLES_TAB`).
* `CommandMatrix.md` — user/admin command catalogue with permissions, feature gates, and descriptions.
* `Runbook.md` — operator actions for routine tasks and incident handling.
* `Troubleshooting.md` — quick reference for diagnosing common issues.
* `Watchers.md` — background jobs covering schedulers, refreshers, and watchdogs.
* `CollaborationContract.md` — contributor standards, PR review flow, and Codex formatting instructions.
* `development.md` — developer setup notes and contribution workflow guidance.
* `commands.md` — supplemental command reference for operational usage.

### Root-Level Docs
* `README.md` — user-facing overview, installation steps, and configuration guidance for the bot.
* `CHANGELOG.md` — version history for the project.

## Phase 5 — Recruitment Modules

- **Phase 5 : Recruitment Modules**
  - Updated: `!clan` — public profile/entry cards with crest and 💡 reaction toggle.
  - Updated: `!clanmatch` — text-only recruiter panel for mobile use.
  - Updated: `!rec env` — now lists Feature Toggles under Sheets / Config Keys.

## Maintenance Rules
* Update this index whenever documentation files are added, renamed, or removed.
* Any PR that modifies documentation must reflect its changes here and, if structural, call them out in the CollaborationContract.
* Ensure the version shown in this index (currently v0.9.5) matches the bot version in the root `README.md`.

## Cross-References
* `docs/ops/CollaborationContract.md` documents contributor responsibilities and embeds this index under “Documentation Discipline.”
