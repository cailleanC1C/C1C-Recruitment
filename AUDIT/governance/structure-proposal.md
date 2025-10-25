# AUDIT Folder Cleanup Proposal

## Current Pain Points
- Mixed naming conventions (e.g., `20251010_codex_audit_MM_WC`, `20251025_PHASE5`) make chronological browsing inconsistent. Files like `CommandPrefix-Audit.md` and `code-audit-2025-10-25.md` sit beside dated folders, creating a flat list that is hard to scan.
- Cross-cutting documents (e.g., `CoreOps-Packaging-Audit.md`, `SUMMARY_MM_WC`) are interspersed with incident-specific timelines, forcing context switches when looking for a single engagement.
- Diagnostics and follow-up notes (for example, `diagnostics/2025-10-25_clanmatch_panel.md`) do not share a naming convention with the main audit runs.

## Sustainable Structure
```
AUDIT/
  README.md
  governance/
    templates/
      INCIDENT_TEMPLATE.md
      AUDIT_TEMPLATE.md
    naming-standards.md
  legacy/
    <slug>/
      2023-11-04_legacy-discovery.md
      code-map.md
  guardrails/
    <system-scope>/
      2025-10-10_guardrail-review.md
      checklist.md
  diagnostics/
    <incident-slug>/
      2025-10-25_clanmatch-panel.md
      2025-10-26_follow-up.md
  phase-audits/
    <engagement-slug>/
      phases/
        2025-10-13_phase-1_lookup/
          CONFIG_NOTES.md
          ...
        2025-10-15_phase-3_implementation/
          ...
      summary.md
      artifacts/
        EXEC_SUMMARY.md
        FINDINGS.md
```

### Folder Rationale
- **Top-level categories mirror the way teams search for material**: long-lived references go under `legacy/`, recurring compliance work lives under `guardrails/`, active issue triage sits in `diagnostics/`, and the iterative audit workstreams aggregate in `phase-audits/`.
- **`governance/`** holds shared policies, templates, and naming rules so contributors can onboard quickly without scanning through operational artifacts.
- **Slug folders (`<engagement-slug>`, `<incident-slug>`)** cluster everything for a topic together; nested dated files capture the immutable timeline for each action or phase.
- **`phase-audits/<engagement-slug>/phases/`** keeps lookup-heavy phase notes organized while still tying them back to a single engagement summary and artifact bundle.

### Naming Guidelines
1. **Prefix dated material with `YYYY-MM-DD_`** inside each slug so timelines stay sortable while the parent folder advertises the topic (e.g., `phase-audits/clansearch/phases/2025-10-13_phase-1_lookup/`).
2. **Keep deliverable types consistent** (`EXEC_SUMMARY.md`, `FINDINGS.md`, `ARTIFACTS.md`, `PATCH_PLAN.md`, etc.) so automation and search filters stay reliable across categories.
3. **Include a single `summary.md` per slug** for the durable overview, linking to dated files rather than duplicating narratives in multiple places.
4. **Reserve the top level for `README.md` and `governance/` assets** to keep daily contributors focused on the topical folders.

## Implementation Steps
1. **Stand up the topical folders** (`legacy/`, `guardrails/`, `diagnostics/`, `phase-audits/`, `governance/`) and move current artifacts into the matching buckets.
2. **Normalize names** by converting camel or uppercase suffixes to lowercase hyphenated slugs (e.g., `CommandPrefix-Audit.md` → `guardrails/command-prefix/2025-10-10_guardrail-review.md`).
3. **Group legacy lookups** by creating `legacy/<codebase-or-system>/` folders and consolidating historic notes there so long-term references stay together.
4. **Nest phase notes** beneath `phase-audits/<engagement-slug>/phases/` while relocating final deliverables into the sibling `artifacts/` folder.
5. **Update README** with the topical layout and add cross-links (e.g., “Latest diagnostics”) to reduce friction when navigating between categories.

## Transition Tips
- Script the moves with a shell script or Make target to preserve git history (`git mv` in batches per slug).
- Add linting or CI check that enforces `YYYY-MM-DD` prefixes for any new folders inside `AUDIT/`.
- Use index files (`index.md`) inside each slug to summarize contents and link to phases.
- Confirm every Markdown file ends with the guardrail footer (`Doc last updated: … (v0.9.5)`) as the
  final line so automated checks stay green after migrations.

Doc last updated: 2025-10-25 (v0.9.5)
