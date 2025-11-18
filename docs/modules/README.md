# Ops Module Index

This index lists the primary operational modules. Each entry summarizes responsibilities and links to the detailed module doc that should be treated as the canonical reference for future changes.

## Onboarding
- [`Onboarding.md`](Onboarding.md) — questionnaire engine: loads questions from Sheets, applies rules/validation, tracks session state, persists progress, and hands normalized answers to downstream UX layers.

## Welcome
- [`Welcome.md`](Welcome.md) — Discord UX: posts the welcome panel, renders onboarding prompts inside ticket threads, formats recruiter summaries, and orchestrates ticket closure → placement hand-offs.

## Placement
- [`Placement.md`](Placement.md) — reservations ledger, clan math reconciliation, reminder/auto-release jobs, and integration glue between Welcome threads and the recruitment sheets.

## Recruitment
- [`Recruitment.md`](Recruitment.md) — sheet-driven clan roster cache, recruiter/member panels, reservation context, and reporting surfaces.
# Modules Overview

This catalog lists the runtime modules that plug into CoreOps. Use it to locate
entry points, feature toggles, and the deep-dive doc for each surface.

| Module | Role | Primary entry points | Deep-dive references |
| --- | --- | --- | --- |
| **CoreOps** | Routing cog, scheduler, cache façade, health/log surfaces. Owns RBAC checks and lifecycle commands. | `!ops …`, `!perm …`, `/health`, `/ready`, watchdog exits. | [`CoreOps.md`](CoreOps.md)
| **Onboarding** | Thread-first wizard for recruiter questionnaires plus sheet reconciliation. | `!ops onb reload`, `!ops onb check`, `!onb resume`, welcome ticket close handler. | [`Onboarding.md`](Onboarding.md), [`docs/runbooks/Onboarding-Runbook.md`](../runbooks/Onboarding-Runbook.md)
| **Welcome** | Persistent welcome panel, template cache, and watcher-controlled ticket creation. | `!welcome`, `!welcome-refresh`, promo/welcome watchers. | [`Welcome.md`](Welcome.md), [`docs/specs/WelcomeFlow.md`](../specs/WelcomeFlow.md), [`docs/specs/Welcome_Summary_Spec.md`](../specs/Welcome_Summary_Spec.md)
| **Recruitment** | Clan search panels, recruiter dashboard, emoji rendering helpers, and report embeds. | `!clanmatch`, recruiter panel UI, daily recruiter report cron. | [`Recruitment.md`](Recruitment.md), [`docs/reference/Commands.md`](../reference/Commands.md)
| **Placement** | Reservations and seat reconciliation when onboarding closes tickets. Shares adapters with recruitment sheets. | `!reserve`, placement watcher hooks, placement summaries in ops channel. | [`Placement.md`](Placement.md), [`docs/specs/Welcome_Summary_Spec.md`](../specs/Welcome_Summary_Spec.md)
| **Shared / OBS** | Sheets adapters, cache warming, logging templates, watchdog tuning, and feature toggles. Supports every module. | Scheduler refresh jobs, structured logging pipeline, feature toggle bootstrap. | [`docs/ops/Config.md`](../ops/Config.md), [`docs/ops/Watchers.md`](../ops/Watchers.md), [`docs/ops/Logging.md`](../ops/Logging.md), [`docs/reference/ModuleToggles.md`](../reference/ModuleToggles.md)

### Module relationships
- All modules import Sheets data exclusively through the async façade described in
  [`CoreOps.md`](CoreOps.md) to avoid blocking the event loop.
- Feature toggles listed in [`docs/reference/ModuleToggles.md`](../reference/ModuleToggles.md) control each
  module’s boot sequence. Missing toggles default to disabled.
- Module-specific docs retain detailed schemas, workflows, and guardrails. This
  overview intentionally stays short; update the deep-dives for behavioural
  changes and link them here.

Doc last updated: 2025-11-17 (v0.9.7)
