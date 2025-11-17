# ADR-0022 — Module Boundaries: Onboarding vs Welcome (and Update Discipline)
Date: 2025-11-17
Status: Draft

## Context
The codebase defines several major modules, including `coreops`, `onboarding`, `welcome`,
`recruitment`, `placement`, and `shared`. Over time, boundaries blurred—especially between
**onboarding** (question engine) and **welcome** (Discord UX). This caused:
- mixed responsibilities  
- duplicated logic  
- inconsistent help text & summary formatting  
- tests not updated when behaviour changed  
- Codex generating new docs instead of updating existing ones  

This ADR establishes precise module boundaries and defines mandatory update discipline for
tests and documentation.

## Decision

### 1. Onboarding Module = Generic, Discord-Agnostic Questionnaire Engine
The onboarding module owns:
- question definitions, types, rules, skip logic  
- validation of answers  
- session state tracking  
- persistence and sheet mapping  
- lifecycle logging  
- summary **data model** (not formatting)

The onboarding module must **not**:
- create threads, embeds, or Discord content  
- contain UX, wording, or help text  
- depend on Discord runtime  
- contain sheet-column logic outside its explicit mapping layer  

### 2. Welcome Module = Discord-Facing User Experience Layer
The welcome module owns:
- thread creation and lifecycle management  
- presentation of onboarding questions as embeds  
- help texts, user guidance, error messages  
- summary formatting and visuals  
- pings, role notifications, C1C-specific behaviour  
- all interactions and commands that begin or continue onboarding  

The welcome module must **not**:
- contain question rules or skip logic  
- be responsible for sheet mapping  
- contain reusable onboarding engine logic  

### 3. Mandatory Test Updates for Behaviour Changes
Any change affecting behaviour in `modules/**`, `coreops/**`, or `shared/**` requires
updated or new tests in the corresponding folder:
- `tests/onboarding/**`
- `tests/welcome/**`
- `tests/recruitment/**`
- `tests/placement/**`
- `tests/coreops/**` or `tests/shared/**`
- `tests/integration/**`
- `tests/config/**`

Exceptions allowed only for docs-only, CI-only, or comment-only changes with explicit PR notes.

### 4. Mandatory Documentation Updates for User-Facing Changes
If a PR changes user-visible behaviour—commands, help text, onboarding questions, summary
layout, watchers/schedules, or feature toggles—then the PR must update:
- `docs/ops/CommandMatrix.md`
- `docs/ops/Module-<Module>.md`
- `docs/ops/Config.md`
- `docs/_meta/DocStyle.md` (if formatting changed)
- `docs/ops/Architecture.md` (if flows changed)
- `CHANGELOG.md`

New docs may only be created with explicit ADR approval.

## Consequences
- Module responsibilities are stable, reviewable, and enforceable.  
- Tests and docs cannot drift out of sync with behaviour.  
- Codex can no longer invent additional doc files.  
- PRs must explicitly justify missing tests or docs.  
- Future expansions of onboarding flows become safer and cleaner.

Doc last updated: 2025-11-17 (v0.9.7)
