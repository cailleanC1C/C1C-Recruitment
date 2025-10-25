# Recruiter Panel (`!clanmatch`) Failure Diagnostics — 2025-10-25

## Executive summary
- `!clanmatch` now instantiates `RecruiterPanelView` with **four selects and seven buttons**, exceeding Discord’s five-row component budget; the extra pagination buttons trigger a `ValueError` before any embeds post, so the panel never spawns.【F:cogs/recruitment_recruiter.py†L170-L223】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- The `discord.ui.View` layout allocator raises `ValueError("could not find open space for item")` when it cannot fit more components; `RecruiterPanelView.__init__` surfaces this error directly, which `discord.ext.commands` wraps as the logged `CommandInvokeError`.【F:modules/recruitment/views/recruiter_panel.py†L252-L282】【4a2721†L1-L23】
- Legacy Matchmaker code placed exactly five buttons on row 4, so it never hit this limit; the regression began when inline pagination buttons were added without row hints in the ported text-only panel.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1322-L1404】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- Thread resolution, permissions, and feature-flag gating still behave as before; the failure occurs before any channel lookup or send call executes.【F:cogs/recruitment_recruiter.py†L44-L223】【F:cogs/recruitment_recruiter.py†L287-L290】

## Exact exception origin
- **Function:** `RecruiterPanelView._build_components` invoked from `RecruiterPanelView.__init__`.【F:modules/recruitment/views/recruiter_panel.py†L252-L282】【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- **Operation:** `self.add_item(prev_button)` (6th button) calls `discord.ui.View.add_item`, which defers to `_ViewWeights.find_open_space` to assign a row. All five rows are already saturated (four selects consume one row each at width 5; five buttons fill the final row at width 1 apiece).【F:modules/recruitment/views/recruiter_panel.py†L420-L478】
- **Library behaviour:** `_ViewWeights.find_open_space` raises `ValueError("could not find open space for item")` when no rows remain; `View.add_item` propagates the error after removing the button from `_children`.【fe6a93†L1-L7】
- **Stack reconstruction:**
  1. `RecruiterPanelCog.clanmatch` → `RecruiterPanelView(self, ctx.author.id)`【F:cogs/recruitment_recruiter.py†L170-L223】
  2. `RecruiterPanelView.__init__` → `_build_components()`【F:modules/recruitment/views/recruiter_panel.py†L252-L282】
  3. `_build_components` → `self.add_item(prev_button)` / `self.add_item(next_button)`【F:modules/recruitment/views/recruiter_panel.py†L463-L479】
  4. `discord.ui.View.add_item` → `_ViewWeights.find_open_space` → `ValueError("could not find open space for item")`【edba2f†L1-L17】【4a2721†L1-L23】
  5. `discord.ext.commands` wraps the uncaught `ValueError` in `CommandInvokeError`, matching production logs (no bot reply is sent because initialisation failed before message creation).【F:cogs/recruitment_recruiter.py†L170-L223】

## Upstream assumptions and current status
- **Component layout** – The port assumes Discord can host seven buttons alongside four selects without manual row placement. In practice, the 5-row limit with select width=5 leaves no space for the sixth button, breaking the assumption.【F:modules/recruitment/views/recruiter_panel.py†L370-L479】
- **Command gating** – RBAC and feature toggle (`recruiter_panel`) remain unchanged; they still gate entry before view construction.【F:cogs/recruitment_recruiter.py†L150-L290】
- **Thread targeting** – `_resolve_recruiter_panel_channel` only runs after view creation succeeds; channel/thread constraints (fixed thread mode, permissions) were not exercised in the failing path.【F:cogs/recruitment_recruiter.py†L44-L223】
- **Sheets/config inputs** – Roster data and sheet fetchers are untouched at failure time because `_run_search` is never called when view construction aborts.【F:modules/recruitment/views/recruiter_panel.py†L600-L856】

## Repro steps (reasoning)
1. Recruiter issues `!clanmatch` in a guild channel.
2. Command handler passes RBAC checks and instantiates `RecruiterPanelView` to prepare embeds.【F:cogs/recruitment_recruiter.py†L160-L223】
3. `_build_components` adds four selects (rows auto-filled) and five buttons, filling all available component slots.【F:modules/recruitment/views/recruiter_panel.py†L370-L461】
4. When it tries to add the pagination buttons, Discord’s layout allocator cannot find an open slot and raises `ValueError("could not find open space for item")`; the command aborts without sending any message.【F:modules/recruitment/views/recruiter_panel.py†L463-L479】【4a2721†L1-L23】

## Impact analysis
- **User-facing:** Recruiters cannot open or refresh panels anywhere (origin channel or fixed thread). The bot responds with nothing because the command fails mid-execution; production logs show the wrapped `CommandInvokeError` and no embeds appear.【F:cogs/recruitment_recruiter.py†L170-L223】
- **Operational:** No downstream sheet reads or panel registrations occur, so cache/state remain untouched; however, recruiters lose their primary tooling (severity high, matches prod incident severity label).
- **Scope:** All guilds using the unified recruiter panel with the new view are affected once the code path deploys; toggles do not mitigate because the failure happens inside the enabled flow.【F:cogs/recruitment_recruiter.py†L287-L290】

## Root-cause candidates (ranked)
1. **Inline pagination buttons overflow component rows** – *High likelihood (observed)*. Verified by inspecting `_build_components`, component widths, and Discord’s allocator raising the exact error.【F:modules/recruitment/views/recruiter_panel.py†L370-L479】【4a2721†L1-L23】
2. **Destination thread/channel issues** – *Low*. Resolution happens after view creation; failure occurs earlier, so no evidence of channel/permission problems in this incident.【F:cogs/recruitment_recruiter.py†L44-L223】
3. **Roster capacity logic** – *Low*. Sheet parsing is downstream of `_run_search`, which never executes when the view fails to build.【F:modules/recruitment/views/recruiter_panel.py†L600-L856】

## Decision matrix
| Candidate | Error reproduced locally | Matches production stack | Requires independent trigger |
|-----------|-------------------------|---------------------------|-------------------------------|
| Pagination buttons overflow | ☑︎ (layout allocator raises `ValueError`)【F:modules/recruitment/views/recruiter_panel.py†L463-L479】【4a2721†L1-L23】 | ☑︎ (`ValueError` bubbled into `CommandInvokeError`)【F:cogs/recruitment_recruiter.py†L170-L223】 | — |
| Thread/channel resolution | ☐ (not reached) | ☐ (no send attempted) | Requires misconfigured thread permissions beyond current failure【F:cogs/recruitment_recruiter.py†L208-L244】 |
| Roster capacity logic | ☐ (search never runs) | ☐ (no roster reads before crash) | Would need sheet state changes to trigger, absent here【F:modules/recruitment/views/recruiter_panel.py†L600-L856】 |

## Proposed fix options (design only)
- **Reintroduce explicit row assignments** – Mirror the legacy layout by pinning the four selects to rows 0–3 and grouping only five buttons on row 4; move pagination controls to a secondary view or reuse the results message pager. Pros: minimal changes, aligns with working legacy behaviour. Cons: requires alternative UX for pagination and status messaging.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1322-L1404】【F:modules/recruitment/views/recruiter_panel.py†L463-L856】
- **Split pagination controls into a separate view** – Keep filter controls on the main panel, but spawn a child view for page navigation attached to the results embeds (matching the legacy Matchmaker pattern). Pros: retains pagination without row pressure. Cons: extra coordination between panel and results message, added state management.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1229-L1298】【F:modules/recruitment/views/recruiter_panel.py†L600-L856】
- **Adopt Section/Container components** – Use newer Discord section components to embed pagination controls without consuming action rows. Pros: future-proof design. Cons: higher implementation effort, requires testing for client compatibility.【4a2721†L1-L23】

## Follow-ups for ops/docs
- Document the Discord UI row limit (5 rows, selects occupy an entire row) in recruiter panel runbooks to prevent repeat regressions.【F:modules/recruitment/views/recruiter_panel.py†L370-L479】【4a2721†L1-L23】
- Confirm feature toggle defaults in deployment checklists; although toggles worked here, they cannot guard against intra-view layout regressions.【F:cogs/recruitment_recruiter.py†L287-L290】

## Evidence excerpts

**Current view layout (implicit rows, 11 components):**

```python
        cb_select = discord.ui.Select(
            placeholder="CB Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label=label, value=label) for label in CB_CHOICES],
            custom_id="rp_cb",
        )
        cb_select.callback = self._on_cb_select
        self.add_item(cb_select)
        self.cb_select = cb_select  # type: ignore[attr-defined]

        hydra_select = discord.ui.Select(
            placeholder="Hydra Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label=label, value=label) for label in HYDRA_CHOICES],
            custom_id="rp_hydra",
        )
        hydra_select.callback = self._on_hydra_select
        self.add_item(hydra_select)

        chimera_select = discord.ui.Select(
            placeholder="Chimera Difficulty (optional)",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=label) for label in CHIMERA_CHOICES
            ],
            custom_id="rp_chimera",
        )
        chimera_select.callback = self._on_chimera_select
        self.add_item(chimera_select)

        playstyle_select = discord.ui.Select(
            placeholder="Playstyle (optional)",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=label)
                for label in PLAYSTYLE_CHOICES
            ],
            custom_id="rp_style",
        )
        playstyle_select.callback = self._on_playstyle_select
        self.add_item(playstyle_select)

        cvc_button = discord.ui.Button(
            label="CvC: —",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_cvc",
        )
        cvc_button.callback = self._on_cvc_toggle
        self.add_item(cvc_button)

        siege_button = discord.ui.Button(
            label="Siege: —",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_siege",
        )
        siege_button.callback = self._on_siege_toggle
        self.add_item(siege_button)

        roster_button = discord.ui.Button(
            label="Open Spots Only",
            style=discord.ButtonStyle.success,
            custom_id="rp_roster",
        )
        roster_button.callback = self._on_roster_toggle
        self.add_item(roster_button)

        reset_button = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_reset",
        )
        reset_button.callback = self._on_reset
        self.add_item(reset_button)

        search_button = discord.ui.Button(
            label="Search Clans",
            style=discord.ButtonStyle.primary,
            custom_id="rp_search",
        )
        search_button.callback = self._on_search
        self.add_item(search_button)

        prev_button = discord.ui.Button(
            label="◀ Prev Page",
            style=discord.ButtonStyle.secondary,
            custom_id="rp_prev",
        )
        prev_button.callback = self._on_prev_page
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            label="Next Page ▶",
            style=discord.ButtonStyle.primary,
            custom_id="rp_next",
        )
        next_button.callback = self._on_next_page
        self.add_item(next_button)
```
【F:modules/recruitment/views/recruiter_panel.py†L370-L479】

**Legacy implementation (explicit row mapping; no pagination buttons):**

```python
    @discord.ui.select(placeholder="CB Difficulty (optional)", min_values=0, max_values=1, row=0,
                       options=[discord.SelectOption(label=o, value=o) for o in CB_CHOICES])
    async def cb_select(self, itx: discord.Interaction, select: discord.ui.Select):
        ...

    @discord.ui.select(placeholder="Playstyle (optional)", min_values=0, max_values=1, row=3,
                       options=[discord.SelectOption(label=o, value=o) for o in PLAYSTYLE_CHOICES])
    async def playstyle_select(self, itx: discord.Interaction, select: discord.ui.Select):
        ...

    @discord.ui.button(label="CvC: —", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_cvc(self, itx: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Siege: —", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_siege(self, itx: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Open Spots Only", style=discord.ButtonStyle.success, row=4, custom_id="roster_btn")
    async def toggle_roster(self, itx: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.secondary, row=4)
    async def reset_filters(self, itx: discord.Interaction, _btn: discord.ui.Button):
        ...

    @discord.ui.button(label="Search Clans", style=discord.ButtonStyle.primary, row=4, custom_id="cm_search")
    async def search(self, itx: discord.Interaction, _btn: discord.ui.Button):
        ...
```
【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1322-L1406】

**discord.py allocator guard:**

```python
    def find_open_space(self, item: Item) -> int:
        for index, weight in enumerate(self.weights):
            if weight + item.width <= 5:
                return index

        raise ValueError('could not find open space for item')
```
【fe6a93†L1-L7】

## Regression timeline
- `Refactor recruiter panel for inline updates and fixed thread routing` (`195aa4a`, 2025-10-20) introduced the pagination buttons and removed the explicit `row=` annotations that previously constrained components to the 5-row budget.【3aebf3†L1-L2】【8dcb75†L1-L9】
- `refactor: adopt modules-first layout` (`bca778d`, 2025-10-22) moved the new view into `modules/recruitment/` without altering the component list, carrying the overflow forward into production releases.【a42fba†L1-L39】【c53b15†L1-L72】
