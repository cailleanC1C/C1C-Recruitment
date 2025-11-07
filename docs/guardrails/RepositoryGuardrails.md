# Repository Guardrails — Master Specification

**Purpose:** Single source of truth for all constraints that govern this codebase.  
Every audit and CI check validates against this document.

## 1) Repository Structure
- **S-01 Modules-First:** All features live under `modules/<domain>` (e.g., `modules/recruitment`, `modules/placement`, `modules/onboarding`). No top-level feature folders.
- **S-02 Shared = Infra Only:** `shared/` contains cross-bot infrastructure (sheets, cache, telemetry, small pure helpers). No Discord commands, views, or RBAC logic in `shared/`.
- **S-03 Cogs-Only Registration:** All commands register under `cogs/`. No `@commands.command`, `@bot.command`, or `@tree.command` outside `cogs/`.
- **S-04 No Side-Effect Imports:** Importing any `modules/*` file must not register commands, start tasks, or mutate runtime globally.
- **S-05 Single Home per Domain:** Each domain has one canonical home (e.g., CoreOps). No duplicate implementations across `shared/`, `modules/`, or `packages/`.
- **S-06 Packages for Reuse:** Reusable feature-level code lives in `packages/<name>` with `pyproject.toml`. Bots import via that package, not `shared/`.
- **S-07 Audits Live in AUDIT/:** Automated reports and scans go under `AUDIT/<YYYYMMDD>_*`. They must not modify runtime code.
- **S-08 Init Hygiene:** Python packages must have `__init__.py`. No empty placeholder files beyond `__init__.py` and `.gitkeep`.

## 2) Coding & Behavior
- **C-01 Async I/O:** Event handlers must not block. External calls (Sheets, HTTP) are async.
- **C-02 Logging:** Use structured logging helpers; no bare `print`.
- **C-03 Imports:** Prefer absolute imports; no parent (`..`) imports.
- **C-04 Feature Flags:** Sourced from the **Features** sheet as `TRUE`/`FALSE` (case-insensitive normalization).
- **C-05 ENV Surface:** ENV is reserved for tokens, IDs, and infrastructure knobs. Feature flags **must not** live in ENV and are sourced exclusively from the FeatureToggles sheet.
- **C-06 Error Handling:** User-facing errors are friendly; exceptions are logged.
- **C-07 RBAC Centralized:** All role/permission checks use the standard RBAC helpers (no ad-hoc checks).
- **C-08 Single-Message Panels:** Interactive panels (like clan panels) update in place; avoid message spam.
- **C-09 No Legacy Paths:** No imports from removed legacy paths (e.g., top-level `recruitment/`, deprecated shared CoreOps shims, `shared/utils/coreops_*`).
- **C-10 Config Access:** Runtime config is accessed via the common config accessor (not scattered utility readers).

Ah, yeah — the house style in that doc uses **code-style IDs (C-01, F-01, etc.)**, single-sentence bullets, and tight spacing instead of tables or bold headers.
Here’s your feature-toggle section rewritten to **match that exact spec layout and tone**:

### 3) Feature Toggles and Config Policy
* **F-01 Sheet Source:** All feature toggles load from the `RECRUITMENT_SHEET › FeatureToggles` tab. No hard-coded flags or ENV overrides.
* **F-02 Defaults:** Each toggle has an explicit `TRUE` or `FALSE` default stored in the sheet. Missing entries are treated as `FALSE`.
* **F-03 Scope:** Toggles control runtime activation of recruitment modules and experiments. They do not alter infrastructure or cluster-wide settings.
* **F-04 Current Toggles:**
  `member_panel`, `recruiter_panel`, `recruitment_welcome`, `recruitment_reports`,
  `placement_target_select`, `placement_reservations`, `clan_profile`, `welcome_dialog`,
  `WELCOME_ENABLED`, `ENABLE_WELCOME_HOOK`, `ENABLE_PROMO_WATCHER`.
* **F-05 Additions:** New toggles must be added to the sheet and documented here with one-line purpose notes.
* **F-06 Runtime Behavior:** Toggles are evaluated dynamically at startup; no redeploy required solely for configuration updates.
* **F-07 Governance:** Repurposing or retiring a toggle requires ADR approval and removal in the next minor version.

## 3) Documentation
- **D-01 Stable Titles:** No “Phase …” in any doc titles.
- **D-02 Footer (exact):** Last line of every doc: `Doc last updated: YYYY-MM-DD (v0.9.x)`
- **D-03 ENV SSoT:** `docs/ops/Config.md` is authoritative for all ENV keys; `.env.example` must match its key set.
- **D-04 Index:** `docs/README.md` lists and links every doc file under `docs/` with a 1-line blurb.
- **D-05 ADRs:** Architectural decisions are recorded as `docs/adr/ADR-XXXX.md` and linked where relevant.
- **D-06 Audit Discoverability:** Each audit adds files under `AUDIT/*` and a pointer in `CHANGELOG.md`.
- **D-07 Contract Priority:** CollaborationContract.md governs process and must link to this guardrails spec.
- **D-08 No Orphan Docs:** Every doc must be linked from `docs/README.md`.

## 4) Governance & Workflow
- **G-01 Version Control:** Versions (bot, footers, changelog) change only on explicit instruction from the owner.
- **G-02 Codex Scope:** Codex performs only what the PR body instructs—no implicit deletions or moves.
- **G-03 PR Metadata:** PR bodies include the `[meta]...[/meta]` block for labels and milestone.
- **G-04 Docs Discipline:** Any code change that affects docs must update them in the same PR.
- **G-05 Audit-First:** Destructive refactors or removals require a prior audit that proves safety.
- **G-06 Naming:** Filenames are `lower_snake_case.md` (no spaces, no “Phase”).
- **G-07 CI Required:** Guardrail checks must be required status checks on PRs.
- **G-08 Secrets:** No secrets in repo or `.env.example`; use deployment envs.

---

### Verification
Compliance script must check: structure (S), code (C), docs (D), governance (G) and write `AUDIT/<timestamp>_GUARDRAILS/report.md`.

Doc last updated: 2025-11-08 (v0.9.7)
