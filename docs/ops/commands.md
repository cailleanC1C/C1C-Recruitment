# CoreOps help system — Phase 3 + 3b

The help surfaces now pull entirely from the CoreOps cache API and the refreshed
command registry. Operators should confirm both the short tier index and the detailed
views after every deploy.

## `!help` — short index
- **Scope:** Admin-only shortcut (mirrors `!rec help`).
- **Behavior:** Returns a compact embed grouped by tier with one-line blurbs only. The
  embed footer shows `Bot vX.Y.Z · CoreOps vA.B.C`; timestamps are no longer rendered.
- **Usage tip:** Trigger this view after reloads to ensure the tier catalog hydrated from
  the live cache.

### Example (Admin tier excerpt)
```
Admin
- !rec refresh all — Warm every cache bucket (actor logged)
- !rec reload — Reload config + toggles
```

## `!help <command>` — detailed view
- **Scope:** Available to any tier that can see the command in the short index.
- **Behavior:** Expands the command with the detailed copy from the Command Matrix,
  including usage signatures, flag notes, and a reminder that prefixes other than `!rec`
  are supported. The embed banner includes a warning if the caller lacks the required
  tier.
- **Footer:** Version info only; embeds omit timestamps to match the new audit policy.

### Example (Recruiter / Staff)
```
!rec refresh templates
Usage: !rec refresh templates
Tier: Staff (Recruiter role or higher required)
Detail: Warms the templates bucket via the cache service and reports duration, retries,
and next run.
Tip: Run after template edits land in Sheets to ensure new copy reaches welcome panels.
```

### Example (User)
```
!rec ping
Usage: !rec ping
Tier: User
Detail: Simple latency check — no cache interaction required.
Tip: Ask staff to escalate if latency exceeds 250 ms for more than 5 minutes.
```

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
