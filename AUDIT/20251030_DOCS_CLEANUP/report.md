# Docs Cleanup Audit — 2025-10-30

## Summary
- Misplaced guardrail docs: 1
- Index coverage gaps: 1
- Title style violations: 3
- Potential duplicates to monitor: 1
- Broken or redirected links: 0
- Footer mismatches: 0

## Findings
| File | Issue type | Suggested fix |
| --- | --- | --- |
| `docs/guardrails/README.md` | Guardrail summary lived outside `docs/guardrails/` prior to move. | Keep guardrail overviews alongside canonical specs inside `docs/guardrails/` to simplify tooling filters. |
| `docs/README.md` | Index missed multiple docs (ops subpages, guardrail summary) before refresh. | Maintain one-line entries for every Markdown file whenever docs are added or relocated. |
| `docs/Architecture.md`, `docs/modules/CoreOps.md` | Overlapping architecture narratives risk drift between high-level and runtime deep dives. | Schedule a consolidation pass so root architecture doc references the CoreOps deep-dive instead of duplicating details. |
| `docs/adr/ADR-0007-feature-toggles-recruitment-module-boundaries.md` | Heading used forbidden “Phase” keyword. | Retitle rollout stages without “Phase” to satisfy guardrail linting. |
| `docs/epic/EPIC_DailyRecruiterUpdate.md` | Heading used forbidden “Phase” keyword. | Rename future-work section to “Next Steps” style for consistency. |
| `docs/Architecture.md` | Heading used forbidden “Phase” keyword. | Update dependency highlight heading to a neutral label (“Wave”, “Stage”, etc.). |

## Pre-move vs post-move snapshot
- **Before:** Guardrail summary sat at `docs/guardrails.md`, confusing folder-level ownership and causing pytest guard checks to scan the wrong location. Index coverage was partial and several docs titles still contained “Phase”.
- **After:** Guardrail content now resides entirely under `docs/guardrails/`, the docs index enumerates every Markdown file with blurbs, and all title lint findings for “Phase” have been cleared.

## Recommendations
- Adopt a quarterly review of `docs/modules/` content to deduplicate long-form architecture details.
- Add a pre-commit hook that runs `scripts/ci/check_docs.py` locally so title/footer regressions are caught before CI.
- When introducing new guardrail or compliance write-ups, commit them directly under `docs/guardrails/` or `docs/compliance/` to keep automation exclusions accurate.
