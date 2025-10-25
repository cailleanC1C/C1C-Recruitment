## 🧭 C1C Bot Collaboration Ground Rules 

These rules define **how planning and implementation are handled** during bot development.
They apply to **all phases, PRs, and documentation changes**.

---

### 🔹 General Workflow

1. **Planning First, Code Later**

   * No code, no PR prompts until I say **“give me code please.”**
   * Until then, only analyze, plan, or audit.

2. **Information Gaps → Ask, Don’t Assume**

   * If something is missing:
     → ask for the file, or
     → propose a **Codex prompt** to read it.
   * Never invent behavior or structure.

3. **Codex = the Coder**

   * All implementation (new files, fixes, refactors) happens via **Codex PRs**.
   * ChatGPT only prepares the PR prompt.
   * No inline pseudo-code or speculative snippets.

4. **Controlled Progression**

   * Move **one Codex prompt at a time.**
   * Analyze results before the next.
   * Never batch prompts.
   * update relevant docs with EACH PR so documentaion always stays up to date and fresh.
---

### 🔹 Guardrails & Boundaries

* **No hard-coded values.**
  Guild IDs, channel IDs, Sheet tabs, Sheet IDs — always from ENV or Sheet Config.
* **Cogs must export:**
  `async def setup(bot)` only; loader awaits it.
* **External I/O:**
  Fail soft, log once, skip, never block boot.
* **Use public APIs only.**
  CoreOps → `capabilities()`, `refresh_now()` etc.
* **Shortcuts = temporary.**
  Ask first and log cleanup tasks.
* **No new functionality without agreement.**

---

### 🔹 Documentation Discipline

* **Document changes immediately after implementation.**

  * Make Codex **read** the relevant doc files first.
  * Add updates in the **existing format** and section.
  * Follow the structure in the current documentation tree (see `/docs` layout: `adr/`, `ops/`, `contracts/`, `compliance/`).
  * **Documentation Index (v0.9.4):** This index explains the intent and ownership of every file in the documentation tree. It exists so that contributors update the correct references after each development phase or PR.
  * **Quality gate:** All docs must follow [`docs/_meta/DocStyle.md`](../_meta/DocStyle.md) and pass `scripts/ci/check_docs.py`. Environment keys are authoritative in [`docs/ops/Config.md`](../ops/Config.md); keep `.env.example` synchronized.

    * **`/docs/adr/` — Architectural Decision Records**
      * Each ADR (`ADR-XXXX`) captures an approved architectural or systemic decision.
      * `ADR-0000` serves as the template for new records.
      * File a new ADR for every major design or structural change.

    * **`/docs/compliance/`**
      * Houses internal compliance and governance policies.
      * Example: `REPORT_GUARDRAILS.md` details report formatting and safety guardrail standards.

    * **`/docs/contracts/`**
      * Defines long-term, structural interfaces between components.
      * `core_infra.md` documents runtime, Sheets access, and cache relationships.
      * Feature toggle guidance moved into other docs; keep legacy references aligned if `feature_toggles.md` is touched.

    * **`/docs/ops/` — Operational Documentation**
      * `Architecture.md` — detailed system flow, runtime design, and module topology.
      * `Config.md` — environment variables, Config tab mapping, and Sheets schema (including `FEATURE_TOGGLES_TAB`).
      * `CommandMatrix.md` — user/admin command catalogue with permissions, feature gates, and descriptions.
      * `Runbook.md` — operator actions for routine tasks and incident handling.
      * `Troubleshooting.md` — quick reference for diagnosing common issues.
      * `Watchers.md` — background jobs covering schedulers, refreshers, and watchdogs.
      * `CollaborationContract.md` — contributor standards, PR review flow, and Codex formatting instructions.
      * `development.md` — developer setup notes and contribution workflow guidance.
      * `commands.md` — supplemental command reference for operational usage.

    * **Root-Level Docs**
      * `README.md` — user-facing overview, installation steps, and configuration guidance for the bot.
      * `CHANGELOG.md` — version history for the project.

    * **Maintenance Rules**
      * Update this index whenever documentation files are added, renamed, or removed.
      * Any PR that modifies documentation must reflect its changes here and, if structural, call them out in the CollaborationContract.
      * Ensure the version shown in this index (currently v0.9.4) matches the bot version in the root `README.md`.

    * **Cross-References**
      * `docs/ops/CollaborationContract.md` documents contributor responsibilities and embeds this index under “Documentation Discipline.”
      * No new docs or folders may be added without updating this index.
* **Architectural Decisions (ADR):**
  Each significant decision we agree on must be recorded under `docs/adr/` using this template format:

  ```
  ADR-0000 — Architectural Decision Record Template
  Date: YYYY-MM-DD

  Context
  Briefly describe background, constraints, and motivation.

  Decision
  Record the chosen direction and rationale; list rejected alternatives if relevant.

  Consequences
  Note trade-offs, follow-ups, and operational impact.

  Status
  Draft
  ```

  Number new ADRs sequentially.

---

### 🔹 Codex PR Formatting Rules

All Codex prompts must be in **one fenced code block** for clean copy/paste.
CI posts a Guardrails Summary comment with config/docs parity and leak-scan status on
every PR—review it and note remediation in the PR body before appending the metadata block.
Append this footer **at the end** of each PR prompt (not as a header):

```markdown
**Instruction for Codex:**
At the end of the PR **body**, after all sections, append the following metadata block exactly as shown.  
Do **not** put it in the title or commit message.  
Do **not** add any text after it.  
This block must be the **final lines** of the PR body so the workflow can parse labels and milestone correctly.
[meta]
labels: <labels here>
milestone: Harmonize v1.0
[/meta]
```

---

### 🔹 Label Reference (Approved Set)
DO not use any other labels unless approved by caillean first

```
bug, perf, robustness, security, observability, infra, architecture, devx, docs, lint,
typecheck, tests, commands, data, config,
P0, P1, P2, P3, P4,
severity:critical, severity:high, severity:medium, severity:low,
bot:reminder, bot:welcomecrew, bot:matchmaker, bot:achievements,
comp:commands, comp:scheduler, comp:health, comp:config, comp:data-sheets,
comp:cache, comp:roles, comp:onboarding, comp:placement,
comp:ocr, comp:shards, comp:ops-contract,
needs:triage, ready, blocked, help wanted, good first issue
```

---

### 🔹 Source References

Legacy bot clones for reference:

```
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM   → Matchmaker legacy clone
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/WC   → WelcomeCrew legacy clone
```

---

### 🔹 Recap — Always Remember

* Don’t code until asked.
* Don’t guess: ask or read.
* One PR at a time.
* No hard-coding or invention.
* Update docs right after each change.
* Record every major decision as an ADR.
* Keep ENV + Sheet config consistent.
* Stop and ask if unsure.

Doc last updated: 2025-10-22 (v0.9.5)


### Label Reference (Approved Set)

DO not use any other labels unless approved by caillean first

| Name | Color | Description |
|---|---|---|
| architecture | `#5319e7` | Cross-cutting design, interfaces, carve-outs |
| AUDIT | `#f9d0c4` | Code audit, understanding functionality |
| blocked | `#b60205` | Blocked by dependency or decision |
| bot:achievements | `#1d76db` | Achievements/Claims bot |
| bot:matchmaker | `#1d76db` | Matchmaker bot |
| bot:reminder | `#1d76db` | Reminder bot |
| bot:welcomecrew | `#1d76db` | WelcomeCrew bot |
| bug | `#b60205` | Broken behavior or incorrect output |
| codex | `#ffffff` |  |
| comp:cache | `#c5def5` | Caching layers / TTL / cold start |
| comp:commands | `#c5def5` | Text/slash, permissions, UX |
| comp:config | `#c5def5` | Env vars, toggles, secrets, YAML/JSON |
| comp:coreops | `#c5def5` |  |
| comp:data-sheets | `#c5def5` | Google Sheets schema, reads/writes, adapters |
| comp:emoji | `#c5def5` |  |
| comp:health | `#c5def5` | Health endpoint, digest, diagnostics |
| comp:modules | `#c5def5` |  |
| comp:ocr | `#c5def5` | Image parsing pipeline |
| comp:onboarding | `#c5def5` | Tickets, welcome flow, forms |
| comp:ops | `#cccccc` |  |
| comp:ops-contract | `#c5def5` | Ops parity: ping/health/digest/reload |
| comp:placement | `#c5def5` | Clan matching, recruiters, moves |
| comp:recruitment | `#c5def5` |  |
| comp:roles | `#c5def5` | Role grants, achievements, approvals |
| comp:scheduler | `#c5def5` | Jobs, timers, offsets |
| comp:shards | `#c5def5` | Shard/mercy tracking logic |
| comp:shared | `#c5def5` |  |
| config | `#006b75` | Env vars, toggles, YAML/JSON config, secrets |
| data | `#4e0e7b` | Sheets schema, caching, adapters, migrations |
| devx | `#c2e0c6` | Developer experience, tooling friction |
| docs | `#0b75a8` | README, guides, runbooks |
| duplicate | `#cfd3d7` | This issue or pull request already exists |
| enhancement | `#a2eeef` | New feature or request |
| good first issue | `#7057ff` | Low-risk starter task |
| guardrails | `#e99695` |  |
| help wanted | `#008672` | Community contributions welcome |
| infra | `#6f42c1` | Hosting, deployment, CI/CD, runtime |
| invalid | `#e4e669` | This doesn't seem right |
| lint | `#000000` | Ruff/formatting cleanups |
| maintenance | `#000000` | maintenance |
| needs:triage | `#fef2c0` | Awaiting label & priority |
| observability | `#1d76db` | Logs, metrics, traces, health, diagnostics |
| P0 | `#ee0701` | CRITICAL — user-visible breakage / hotfix |
| P1 | `#d93f0b` | HIGH — core function degraded / urgent |
| P2 | `#fbca04` | MEDIUM — important, not blocking |
| P3 | `#cccccc` | LOW — cleanup/polish |
| P4 | `#e6e6e6` | VERY LOW — icebox/backlog |
| perf | `#0e8a16` | Performance regression or optimization |
| ready | `#0e8a16` | Groomed and ready for pickup |
| robustness | `#0366d6` | Resilience: retries, backoff, failure handling |
| security | `#e99695` | Vulnerabilities, secrets, permissions/ACL |
| severity:critical | `#ee0701` | Mirrors P0 |
| severity:high | `#d93f0b` | Mirrors P1 |
| severity:low | `#cccccc` | Mirrors P3/P4 |
| severity:medium | `#fbca04` | Mirrors P2 |
| telemetry | `#780b1a` |  |
| tests | `#a2eeef` | Unit/integration/e2e tests |
| typecheck | `#bfdadc` | mypy/pyright typing issues |
| wontfix | `#ffffff` | This will not be worked on |

Doc last updated: 2025-10-27 (v0.9.7)
