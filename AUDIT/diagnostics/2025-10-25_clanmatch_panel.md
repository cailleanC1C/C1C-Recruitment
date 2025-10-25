# Recruiter Panel (`!clanmatch`) Failure Diagnostics — 2025-10-25

## Executive summary
- `!clanmatch` now instantiates `RecruiterPanelView` with **four selects and seven buttons**, exceeding Discord’s five-row component budget; the extra pagination buttons trigger a `ValueError` before any embeds post, so the panel never spawns.【F:cogs/recruitment_recruiter.py†L170-L223】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- The `discord.ui.View` layout allocator raises `ValueError("could not find open space for item")` when it cannot fit more components; `RecruiterPanelView.__init__` surfaces this error directly, which `discord.ext.commands` wraps as the logged `CommandInvokeError`.【F:modules/recruitment/views/recruiter_panel.py†L252-L282】【6e476c†L1-L36】
- Legacy Matchmaker code placed exactly five buttons on row 4, so it never hit this limit; the regression began when inline pagination buttons were added without row hints in the ported text-only panel.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1322-L1404】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- Thread resolution, permissions, and feature-flag gating still behave as before; the failure occurs before any channel lookup or send call executes.【F:cogs/recruitment_recruiter.py†L44-L223】【F:cogs/recruitment_recruiter.py†L287-L290】

## Exact exception origin
- **Function:** `RecruiterPanelView._build_components` invoked from `RecruiterPanelView.__init__`.【F:modules/recruitment/views/recruiter_panel.py†L252-L282】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- **Operation:** `self.add_item(prev_button)` (6th button) calls `discord.ui.View.add_item`, which defers to `_ViewWeights.find_open_space` to assign a row. All five rows are already saturated (four selects consume one row each at width 5; five buttons fill the final row at width 1 apiece).【F:modules/recruitment/views/recruiter_panel.py†L420-L478】【9d3cf2†L1-L6】
- **Library behaviour:** `_ViewWeights.find_open_space` raises `ValueError("could not find open space for item")` when no rows remain; `View.add_item` propagates the error after removing the button from `_children`.【6e476c†L1-L36】【80dc7d†L1-L15】
- **Stack reconstruction:**
  1. `RecruiterPanelCog.clanmatch` → `RecruiterPanelView(self, ctx.author.id)`【F:cogs/recruitment_recruiter.py†L170-L223】
  2. `RecruiterPanelView.__init__` → `_build_components()`【F:modules/recruitment/views/recruiter_panel.py†L252-L282】
  3. `_build_components` → `self.add_item(prev_button)` / `self.add_item(next_button)`【F:modules/recruitment/views/recruiter_panel.py†L463-L479】
  4. `discord.ui.View.add_item` → `_ViewWeights.find_open_space` → `ValueError("could not find open space for item")`【80dc7d†L1-L15】【6e476c†L1-L36】
  5. `discord.ext.commands` wraps the uncaught `ValueError` in `CommandInvokeError`, matching production logs (no bot reply is sent because initialisation failed before message creation).【F:cogs/recruitment_recruiter.py†L170-L223】

## Upstream assumptions and current status
- **Component layout** – The port assumes Discord can host seven buttons alongside four selects without manual row placement. In practice, the 5-row limit with select width=5 leaves no space for the sixth button, breaking the assumption.【F:modules/recruitment/views/recruiter_panel.py†L370-L479】【9d3cf2†L1-L6】
- **Command gating** – RBAC and feature toggle (`recruiter_panel`) remain unchanged; they still gate entry before view construction.【F:cogs/recruitment_recruiter.py†L150-L290】
- **Thread targeting** – `_resolve_recruiter_panel_channel` only runs after view creation succeeds; channel/thread constraints (fixed thread mode, permissions) were not exercised in the failing path.【F:cogs/recruitment_recruiter.py†L44-L223】
- **Sheets/config inputs** – Roster data and sheet fetchers are untouched at failure time because `_run_search` is never called when view construction aborts.【F:modules/recruitment/views/recruiter_panel.py†L600-L856】

## Repro steps (reasoning)
1. Recruiter issues `!clanmatch` in a guild channel.
2. Command handler passes RBAC checks and instantiates `RecruiterPanelView` to prepare embeds.【F:cogs/recruitment_recruiter.py†L160-L223】
3. `_build_components` adds four selects (rows auto-filled) and five buttons, filling all available component slots.【F:modules/recruitment/views/recruiter_panel.py†L370-L461】
4. When it tries to add the pagination buttons, Discord’s layout allocator cannot find an open slot and raises `ValueError("could not find open space for item")`; the command aborts without sending any message.【F:modules/recruitment/views/recruiter_panel.py†L463-L479】【6e476c†L1-L36】

## Impact analysis
- **User-facing:** Recruiters cannot open or refresh panels anywhere (origin channel or fixed thread). The bot responds with nothing because the command fails mid-execution; production logs show the wrapped `CommandInvokeError` and no embeds appear.【F:cogs/recruitment_recruiter.py†L170-L223】
- **Operational:** No downstream sheet reads or panel registrations occur, so cache/state remain untouched; however, recruiters lose their primary tooling (severity high, matches prod incident severity label).
- **Scope:** All guilds using the unified recruiter panel with the new view are affected once the code path deploys; toggles do not mitigate because the failure happens inside the enabled flow.【F:cogs/recruitment_recruiter.py†L287-L290】

## Root-cause candidates (ranked)
1. **Inline pagination buttons overflow component rows** – *High likelihood (observed)*. Verified by inspecting `_build_components`, component widths, and Discord’s allocator raising the exact error.【F:modules/recruitment/views/recruiter_panel.py†L370-L479】【9d3cf2†L1-L6】【6e476c†L1-L36】
2. **Destination thread/channel issues** – *Low*. Resolution happens after view creation; failure occurs earlier, so no evidence of channel/permission problems in this incident.【F:cogs/recruitment_recruiter.py†L44-L223】
3. **Roster capacity logic** – *Low*. Sheet parsing is downstream of `_run_search`, which never executes when the view fails to build.【F:modules/recruitment/views/recruiter_panel.py†L600-L856】

## Decision matrix
| Candidate | Error reproduced locally | Matches production stack | Requires independent trigger |
|-----------|-------------------------|---------------------------|-------------------------------|
| Pagination buttons overflow | ☑︎ (layout allocator raises `ValueError`)【F:modules/recruitment/views/recruiter_panel.py†L463-L479】【6e476c†L1-L36】 | ☑︎ (`ValueError` bubbled into `CommandInvokeError`)【F:cogs/recruitment_recruiter.py†L170-L223】 | — |
| Thread/channel resolution | ☐ (not reached) | ☐ (no send attempted) | Requires misconfigured thread permissions beyond current failure【F:cogs/recruitment_recruiter.py†L208-L244】 |
| Roster capacity logic | ☐ (search never runs) | ☐ (no roster reads before crash) | Would need sheet state changes to trigger, absent here【F:modules/recruitment/views/recruiter_panel.py†L600-L856】 |

## Proposed fix options (design only)
- **Reintroduce explicit row assignments** – Mirror the legacy layout by pinning the four selects to rows 0–3 and grouping only five buttons on row 4; move pagination controls to a secondary view or reuse the results message pager. Pros: minimal changes, aligns with working legacy behaviour. Cons: requires alternative UX for pagination and status messaging.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1322-L1404】【F:modules/recruitment/views/recruiter_panel.py†L463-L856】
- **Split pagination controls into a separate view** – Keep filter controls on the main panel, but spawn a child view for page navigation attached to the results embeds (matching the legacy Matchmaker pattern). Pros: retains pagination without row pressure. Cons: extra coordination between panel and results message, added state management.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1229-L1298】【F:modules/recruitment/views/recruiter_panel.py†L600-L856】
- **Adopt Section/Container components** – Use newer Discord section components to embed pagination controls without consuming action rows. Pros: future-proof design. Cons: higher implementation effort, requires testing for client compatibility.【6e476c†L1-L36】

## Follow-ups for ops/docs
- Document the Discord UI row limit (5 rows, selects occupy an entire row) in recruiter panel runbooks to prevent repeat regressions.【9d3cf2†L1-L6】【6e476c†L1-L36】
- Confirm feature toggle defaults in deployment checklists; although toggles worked here, they cannot guard against intra-view layout regressions.【F:cogs/recruitment_recruiter.py†L287-L290】
