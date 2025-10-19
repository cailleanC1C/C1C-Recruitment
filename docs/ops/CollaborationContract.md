## 🧭 C1C Bot Collaboration Ground Rules 

These rules define **how planning and implementation are handled** during bot development.
They apply to **all phases, PRs, and documentation changes**.

---

### 🔹 General Workflow

1. **Planning First, Code Later**

   * No code until I say **“give me code please.”**
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
AUDIT/20251010_src/MM   → Matchmaker legacy clone
AUDIT/20251010_src/WC   → WelcomeCrew legacy clone
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

