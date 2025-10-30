# 🧭 C1C Bot Collaboration Contract (v1.0)

**Purpose**
Single source of truth for how we work (you ↔ ChatGPT ↔ Codex), how pull requests are prepared, and where Codex finds guardrails/CI policy. This file is the only thing you need to hand me.

---

## 1) Workflow & Communication

### 1.1 Planning before coding

* No code and no PR prompt until you say: **“give me code please.”**
* Before that: analysis, audits, plans.
* If anything’s missing, I will ask for the file or propose a Codex read of repo paths. No invention.

### 1.2 Stepwise execution

* **One Codex prompt at a time.**
* Review results, then proceed.
* Each PR must update affected docs in the same PR.

### 1.3 Roles

* **ChatGPT**: planner, auditor, reviewer.
* **Codex**: implementer (creates/edits files via PR).

---

## 2) Boundaries & Guardrails (must-follow)

* **No hard-coded values** (IDs/tabs/tokens). Use ENV or Sheet Config.
* **Cogs export only** `async def setup(bot)`.
* **I/O**: fail soft, log once, don’t block boot.
* **Public APIs only** (CoreOps/shared).
* **Shortcuts**: ask first; log cleanup tasks.
* **No new functionality** without explicit approval (architectural changes require an ADR).

---

## 3) Documentation Discipline

### 3.1 Immediate updates

* Codex **reads** existing docs first, then updates in-place, preserving structure/format.
* All doc changes ride in the **same PR** as the code change.

### 3.2 Folder map (authoritative)

| Folder             | Purpose                                                                     |
| ------------------ | --------------------------------------------------------------------------- |
| `docs/adr/`        | Architectural Decision Records (ADR-XXXX).                                  |
| `docs/ops/`        | Ops docs: Config schema, CommandMatrix, Runbook, Troubleshooting, Watchers. |
| `docs/contracts/`  | Long-lived standards (this contract).                                       |
| `docs/guardrails/` | Guardrail & CI policy specs (e.g., `RepositoryGuardrails.md`).              |
| `docs/compliance/` | Audit and guardrail reports (e.g., `REPORT_GUARDRAILS.md`).                 |

### 3.3 ADR template

```
ADR-0000 — Title
Date: YYYY-MM-DD

Context
Decision
Consequences
Status: Draft/Approved
```

### 3.4 Footer & version rules

* Footer format (exact): `Doc last updated: YYYY-MM-DD (vX.Y.Z)`
* Update date **only** if content changed; use today’s **UTC** date.
* Version bumps **only** when explicitly approved in the PR via `[approval]`.

### 3.5 Required PR blocks

```markdown
[approval]
version: vX.Y.Z          # optional; include only when approved
footer_date: YYYY-MM-DD  # optional; include only when approved
[/approval]

[meta]
labels: <labels here>
milestone: Harmonize v1.0
[/meta]
```

---

## 4) Codex PR Formatting Rules

* Entire PR prompt in **one fenced code block**.
* Append the `[meta]` block as the **final lines** of the PR body (no text after it).
* Use **approved label names only** (see §6).
* Do not move/delete files unless explicitly instructed in the PR body.
* Before editing guardrail/compliance docs, Codex must read:

  * `docs/guardrails/RepositoryGuardrails.md`
  * `docs/compliance/REPORT_GUARDRAILS.md`

---

## 5) Repository Lookup Map (for Codex)

| Topic                           | Source                                                |
| ------------------------------- | ----------------------------------------------------- |
| Repo structure & CI constraints | `docs/guardrails/RepositoryGuardrails.md`             |
| Compliance/audit snapshots      | `docs/compliance/REPORT_GUARDRAILS.md`                |
| Contribution & PR process       | `docs/contracts/CollaborationContract.md` (this file) |
| Config & ENV schema             | `docs/ops/Config.md`                                  |
| Architectural decisions         | `docs/adr/`                                           |

---

## 6) Label Reference (Approved Set — full list)

> Source of truth normally lives at `.github/labels/labels.json`, but because ChatGPT can’t read it, the **entire approved set** is embedded here. **Use only these.**

| Name              | Color     | Description                                    |
| ----------------- | --------- | ---------------------------------------------- |
| architecture      | `#5319e7` | Cross-cutting design, interfaces, carve-outs   |
| AUDIT             | `#f9d0c4` | Code audit, understanding functionality        |
| blocked           | `#b60205` | Blocked by dependency or decision              |
| bot:achievements  | `#1d76db` | Achievements/Claims bot                        |
| bot:matchmaker    | `#1d76db` | Matchmaker bot                                 |
| bot:reminder      | `#1d76db` | Reminder bot                                   |
| bot:welcomecrew   | `#1d76db` | WelcomeCrew bot                                |
| bug               | `#b60205` | Broken behavior or incorrect output            |
| codex             | `#ffffff` | Codex-internal PRs or scaffolding              |
| comp:cache        | `#c5def5` | Caching layers / TTL / cold start              |
| comp:commands     | `#c5def5` | Text/slash, permissions, UX                    |
| comp:config       | `#c5def5` | Env vars, toggles, secrets, YAML/JSON          |
| comp:coreops      | `#c5def5` | CoreOps surface / contracts                    |
| comp:data-sheets  | `#c5def5` | Google Sheets schema, reads/writes, adapters   |
| comp:emoji        | `#c5def5` | Emoji assets and usage                         |
| comp:health       | `#c5def5` | Health endpoint, digest, diagnostics           |
| comp:modules      | `#c5def5` | Module boundaries, loaders                     |
| comp:ocr          | `#c5def5` | Image parsing pipeline                         |
| comp:onboarding   | `#c5def5` | Tickets, welcome flow, forms                   |
| comp:ops          | `#cccccc` | Operational surface/commands                   |
| comp:ops-contract | `#c5def5` | Ops parity: ping/health/digest/reload          |
| comp:placement    | `#c5def5` | Clan matching, recruiters, moves               |
| comp:recruitment  | `#c5def5` | Recruitment flows & panels                     |
| comp:roles        | `#c5def5` | Role grants, achievements, approvals           |
| comp:scheduler    | `#c5def5` | Jobs, timers, offsets                          |
| comp:shards       | `#c5def5` | Shard/mercy tracking logic                     |
| comp:shared       | `#c5def5` | Shared helpers & adapters                      |
| config            | `#006b75` | Env vars, toggles, YAML/JSON config, secrets   |
| data              | `#4e0e7b` | Sheets schema, caching, adapters, migrations   |
| devx              | `#c2e0c6` | Developer experience, tooling friction         |
| docs              | `#0b75a8` | README, guides, runbooks                       |
| duplicate         | `#cfd3d7` | This issue or pull request already exists      |
| enhancement       | `#a2eeef` | New feature or request                         |
| good first issue  | `#7057ff` | Low-risk starter task                          |
| guardrails        | `#e99695` | Guardrail specs & checks                       |
| help wanted       | `#008672` | Community contributions welcome                |
| infra             | `#6f42c1` | Hosting, deployment, CI/CD, runtime            |
| invalid           | `#e4e669` | This doesn't seem right                        |
| lint              | `#000000` | Ruff/formatting cleanups                       |
| maintenance       | `#000000` | Routine maintenance                            |
| needs:triage      | `#fef2c0` | Awaiting label & priority                      |
| observability     | `#1d76db` | Logs, metrics, traces, health, diagnostics     |
| P0                | `#ee0701` | CRITICAL — user-visible breakage / hotfix      |
| P1                | `#d93f0b` | HIGH — core function degraded / urgent         |
| P2                | `#fbca04` | MEDIUM — important, not blocking               |
| P3                | `#cccccc` | LOW — cleanup/polish                           |
| P4                | `#e6e6e6` | VERY LOW — icebox/backlog                      |
| perf              | `#0e8a16` | Performance regression or optimization         |
| ready             | `#0e8a16` | Groomed and ready for pickup                   |
| robustness        | `#0366d6` | Resilience: retries, backoff, failure handling |
| security          | `#e99695` | Vulnerabilities, secrets, permissions/ACL      |
| severity:critical | `#ee0701` | Mirrors P0                                     |
| severity:high     | `#d93f0b` | Mirrors P1                                     |
| severity:low      | `#cccccc` | Mirrors P3/P4                                  |
| severity:medium   | `#fbca04` | Mirrors P2                                     |
| telemetry         | `#780b1a` | Telemetry signals & pipelines                  |
| tests             | `#a2eeef` | Unit/integration/e2e tests                     |
| typecheck         | `#bfdadc` | mypy/pyright typing issues                     |
| wontfix           | `#ffffff` | Will not be worked                             |

---

## 7) Guardrails & CI placement rules (docs hygiene)

* **Docs live only in their proper homes**:

  * guardrail/CI specs → `docs/guardrails/`
  * compliance reports → `docs/compliance/`
  * contracts & contributor rules → `docs/contracts/`
  * ops docs → `docs/ops/`
* **Titles**: no “Phase …” in doc titles.
* **Indexing**: every doc must be linked from `docs/README.md`.
* **ENV SSoT**: `docs/ops/Config.md` is authoritative; `.env.example` must match.

---

## 8) AUDIT folder policy (strict)

* **For Codex and CI scans/tests/checks**: **ignore** `AUDIT/` completely.

  * Do not analyze, lint, type-check, or include `AUDIT/` content in guardrail calculations.
* **For new audits**: write outputs **into** `AUDIT/<YYYYMMDD>_*` and **add a pointer** entry to `CHANGELOG.md`.
* **Renames/moves**: audits **must not** modify runtime code; they are **read-only evidence**.
* **PR instructions** must explicitly exclude `AUDIT/` from test/scan steps.

---

## 9) Governance & Workflow

* **Version control**: repo versions and footer dates change **only** with explicit approval.
* **Audit-first** for destructive refactors/removals.
* **Docs parity**: code changes that affect docs must update them in the same PR.
* **No secrets** in repo or `.env.example`.

---

## 10) Final checklist (quick scan)

* ☐ Did we say “give me code please”?
* ☐ One Codex prompt only?
* ☐ No hard-coded IDs/tabs?
* ☐ Docs updated (same PR)?
* ☐ ADR filed (if architectural)?
* ☐ ENV + Sheets in sync?
* ☐ Excluded `AUDIT/` from scans/tests?
* ☐ `[meta]` is the last lines in PR body?

---

Doc last updated: 2025-10-30 (v0.9.7)
