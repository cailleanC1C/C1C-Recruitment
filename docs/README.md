# Documentation Index

This index links every document under `docs/` so contributors can locate the correct
reference quickly.

## Root documentation
- [Architecture Overview](Architecture.md) — system runtime map and module topology.
- [Development Reference](development.md) — pointer to the canonical ops development guide.
- [Documentation Index](README.md) — this page.

## Meta
- [_meta/DocStyle.md](./_meta/DocStyle.md) — contract for titles, footers, and docs linting.

## Operational guides
- [ops/Architecture.md](ops/Architecture.md) — CoreOps architecture and feature-gating notes.
- [ops/CommandMatrix.md](ops/CommandMatrix.md) — tiered command catalogue with short blurbs.
- [ops/commands.md](ops/commands.md) — detailed command behavior notes per surface.
- [ops/Config.md](ops/Config.md) — authoritative environment keys and sheet config mapping.
- [ops/development.md](ops/development.md) — CoreOps development guardrails and runtime caveats.
- [ops/module-toggles.md](ops/module-toggles.md) — FeatureToggles worksheet reference.
- [ops/Runbook.md](ops/Runbook.md) — startup, refresh, and incident handling procedures.
- [ops/Troubleshooting.md](ops/Troubleshooting.md) — quick diagnostics for common failures.
- [ops/Watchers.md](ops/Watchers.md) — watcher lifecycle, cron cadence, and cache strategy.

## Contracts
- [contracts/CollaborationContract.md](contracts/CollaborationContract.md) — contributor standards and review expectations.
- [contracts/core_infra.md](contracts/core_infra.md) — runtime, deployment, and watchdog contract for infra.

## Compliance
- [compliance/REPORT_GUARDRAILS.md](compliance/REPORT_GUARDRAILS.md) — reporting format and safety guardrails.

## Architectural decision records
- [adr/README.md](adr/README.md) — ADR purpose and local index.
- [adr/ADR-0000-template.md](adr/ADR-0000-template.md) — template for new architectural decision records.
- [adr/ADR-0001-sheets-access-layer.md](adr/ADR-0001-sheets-access-layer.md) — adopts the async cached Sheets access layer.
- [adr/ADR-0002-cache-telemetry-wrapper.md](adr/ADR-0002-cache-telemetry-wrapper.md) — standardizes telemetry via the public cache API.
- [adr/ADR-0003-coreops-command-contract.md](adr/ADR-0003-coreops-command-contract.md) — unifies the CoreOps command surface and RBAC gates.
- [adr/ADR-0004-help-system-short-vs-detailed.md](adr/ADR-0004-help-system-short-vs-detailed.md) — defines short vs detailed help embeds.
- [adr/ADR-0005-reload-vs-refresh.md](adr/ADR-0005-reload-vs-refresh.md) — separates config reloads from cache refresh behavior.
- [adr/ADR-0006-startup-preloader-bot-info-cron.md](adr/ADR-0006-startup-preloader-bot-info-cron.md) — mandates startup warmers and bot_info cron checks.
- [adr/ADR-0007-feature-toggles-recruitment-module-boundaries.md](adr/ADR-0007-feature-toggles-recruitment-module-boundaries.md) — scopes recruitment modules behind feature toggles.
- [adr/ADR-0008-emoji-pipeline-port.md](adr/ADR-0008-emoji-pipeline-port.md) — ports the emoji pipeline for module-first runtime.
- [adr/ADR-0009-recruiter-panel-text-only.md](adr/ADR-0009-recruiter-panel-text-only.md) — keeps recruiter panels text-only for fast iterations.
- [adr/ADR-0010-clan-profile-with-emoji.md](adr/ADR-0010-clan-profile-with-emoji.md) — adds crest attachments to public clan cards.
- [adr/ADR-0011.md](adr/ADR-0011.md) — consolidates recruitment modules and prepares `!clansearch`.

## How to update docs
Follow the rules in [contracts/CollaborationContract.md](contracts/CollaborationContract.md) and the
style guide in [_meta/DocStyle.md](./_meta/DocStyle.md) whenever documentation changes.

Doc last updated: 2025-10-22 (v0.9.5)
