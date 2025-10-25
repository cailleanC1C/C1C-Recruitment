# AUDIT Quick Reference

The `AUDIT/` workspace now follows topical buckets to keep long-running artifacts easy to
find:

| Folder | When to use it |
| --- | --- |
| [`governance/`](governance/) | Shared policies, templates, and structural decisions. |
| [`legacy/`](legacy/) | Frozen code exports and historical lookups kept for reference. |
| [`guardrails/`](guardrails/) | Compliance runs and automated guardrail outputs grouped by scope. |
| [`diagnostics/`](diagnostics/) | Point-in-time investigations for incidents or bug hunts. |
| [`phase-audits/`](phase-audits/) | Multi-phase audit engagements with summaries, artifacts, and dated working notes. |

## Navigation Tips
- Each topical slug includes an `index.md` for quick orientation and linkouts.
- Dated files use the `YYYY-MM-DD_` prefix so timelines remain sortable inside a slug.
- Append new findings under the relevant topic instead of creating new top-level folders.

## Recent Highlights
- WelcomeCrew modernization notes, artifacts, and summaries live under
  [`phase-audits/welcomecrew-modernization/`](phase-audits/welcomecrew-modernization/).
- Command prefix and CoreOps guardrail runs are captured under
  [`guardrails/`](guardrails/).
- Legacy bot code exports remain available under
  [`legacy/clanmatch-welcomecrew/`](legacy/clanmatch-welcomecrew/).

Doc last updated: 2025-10-25 (v0.9.5)
