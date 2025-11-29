# Promo Summary Embeds — Readability Spec (v1.0)

> NOTE: This spec mirrors the Welcome Summary layout style (sections, inline pairs, number formatting),
> but adapts the sections and field groupings to each promo flow:
> - `promo.r` — Returning player requests
> - `promo.m` — Member move requests
> - `promo.l` — Leadership-initiated move requests

## Overview

- Promo summary embeds reuse the **same visual style** as the Welcome Summary:
  - Section headers
  - Inline field pairs with `•` separator
  - Number abbreviation (`K` / `M`)
- Returning/member move flows continue to honour the **sheet-driven visibility rules** (`skip` / `optional` decisions).
- Leadership move embeds now use a dedicated layout keyed off the `pl_` answer set (not the welcome layout):
  - Player & reporter lines draw from `pl_player_name`, `pl_reporter`, and clan fields.
  - Inline pairs keep difficulty + clash data on the same line (Hydra/Chimera, CvC points inline with CvC state).
  - War-mode details show Siege participation on every leadership summary; Siege detail is conditional.
- Inline formatting keeps Hydra and Chimera clash averages alongside their difficulty answers, and CvC points inline with priority.
- Each promo flow has its own **section layout**, but all use a shared builder pattern.

---

## Common behaviour across all promo flows

The following rules apply to all promo flows (`promo.r`, `promo.m`, `promo.l`) unless stated otherwise.

### Common hide rules

- Skip any field whose rendered value is empty or matches (case-insensitive):
  - `0`
  - `no`
  - `none`
  - `dunno`
- **Exception:** Siege participation always appears, even when the answer is “No”.
- Siege detail fields are hidden when Siege participation resolves to an empty/“no”/“none” value.

### Common number formatting

These fields use abbreviated numeric formatting:

- Power (where present)
- Average Hydra Clash score
- Average Chimera Clash score
- Minimum CvC points

Formatting rules:

- Values below `1,000` remain unchanged.
- From `1,000` to `< 1,000,000`: display as `### K` (rounded, no decimals).
- From `1,000,000` upwards: display as `#.# M` (one decimal maximum).
  - Trailing `.0` can be collapsed (e.g. `1.0 M` → `1 M` if desired by implementation).

### Common CvC priority mapping

Where the sheet stores numeric CvC priority values, display labels are:

| Sheet value | Display       |
| ----------- | ------------- |
| `1`         | Low           |
| `2`         | Low-Medium    |
| `3`         | Medium        |
| `4`         | High-Medium   |
| `5`         | High          |

If the sheet already stores human-readable labels, they are rendered as-is.

### Common visibility handling

- Only answers with a resolved visibility state **other than** `skip` are rendered (for flows that use sheet-driven visibility).
- If summary generation fails, a promo-scoped fallback embed is posted with the message
  **“Promo summary unavailable — please ping @RecruitmentCoordinator”**.

---

## `promo.r` — Returning player requests

### Field mapping (gid → display label)

> gid names below follow the `pr_…` naming pattern and should match the Promo sheet.  
> Where exact gid values are not yet confirmed, they can be filled in once the sheet is final.

| gid             | Label                         | Notes                                                                 |
| --------------- | ----------------------------- | --------------------------------------------------------------------- |
| `pr_ign`        | Player                        | Returning player’s in-game name                                      |
| `pr_power`      | Power                         | Abbreviated number formatting                                        |
| `pr_level_detail` | Bracket                     | Single-select bracket; inline with Power                             |
| `pr_playstyle`  | Playstyle                     |                                                                       |
| `pr_prev_clan`  | Last clan played in          | Optional; may be omitted if unknown                                  |
| `pr_clan`       | Looking for                   | Intended future clan type / goal                                     |
| `pr_CB`         | Clan Boss (one-key top chest) | Past performance at time of leaving                                  |
| `pr_hydra_diff` | Hydra                         | Past difficulty                                                       |
| `pr_hydra_clash`| Avg Hydra Clash               | Inline with Hydra; abbreviated number formatting                     |
| `pr_chimera_diff` | Chimera                     | Past difficulty                                                       |
| `pr_chimera_clash` | Avg Chimera Clash          | Inline with Chimera; abbreviated number formatting                   |
| `pr_siege`      | Siege participation           | Always rendered                                                       |
| `pr_siege_detail` | Siege setup                 | Hidden when `pr_siege` is empty/“no”/“none”                          |
| `pr_cvc`        | CvC priority                  | Uses shared CvC mapping where numeric                                |
| `pr_cvc_points` | Minimum CvC points            | Abbreviated number formatting                                        |
| `pr_return_reason` | Reason for break           | Optional free-text, truncated at ~200 chars if needed                |
| `pr_return_change` | What changed / why now     | Optional; shows what allows them to return now                       |
| `pr_notes`      | Anything else we should know  | Optional free-text, truncated at ~200–300 chars                      |

### Sections & layout

1. **Identity & return intent**  
   - `pr_ign`  
   - `pr_power` + `pr_level_detail` (inline)  
   - `pr_playstyle`  
   - `pr_prev_clan`  
   - `pr_clan`

2. **Past progress & bossing**  
   - `pr_CB`  
   - `pr_hydra_diff` + `pr_hydra_clash` (inline)  
   - `pr_chimera_diff` + `pr_chimera_clash` (inline)

3. **War modes**  
   - `pr_siege`  
   - `pr_siege_detail` (conditional)  
   - `pr_cvc` + `pr_cvc_points` (inline)

4. **Return context & notes**  
   - `pr_return_reason`  
   - `pr_return_change`  
   - `pr_notes`

### Inline formatting examples (`promo.r`)

- `Power: 12.6 M • Bracket: Early Endgame`
- `Hydra: Normal • Avg Hydra Clash: 320 K`
- `Chimera: Easy • Avg Chimera Clash: 240 K`
- `CvC priority: High-Medium • Minimum CvC points: 60 K`

---

## `promo.m` — Member move requests

This flow is initiated by the **member themselves**, focusing on their current placement and the move they’re asking for.

### Field mapping (gid → display label)

> gid names follow the `pm_…` pattern. Some are based on existing logs (`pm_level_detail`, `pm_hydra_diff`, etc).

| gid               | Label                              | Notes                                                                 |
| ----------------- | ---------------------------------- | --------------------------------------------------------------------- |
| `pm_ign`          | Player                             | Member’s in-game name                                                |
| `pm_power`        | Power                              | Abbreviated number formatting                                        |
| `pm_level_detail` | Bracket                            | Inline with Power                                                     |
| `pm_playstyle`    | Playstyle                          |                                                                       |
| `pm_current_clan` | Current clan                       | Source clan                                                           |
| `pm_clan_type`    | Looking for                        | Desired clan type / focus                                            |
| `pm_CB`           | Clan Boss (one-key top chest)      | Current CB performance                                               |
| `pm_hydra_diff`   | Hydra                              | Current difficulty                                                   |
| `pm_hydra_clash`  | Avg Hydra Clash                    | Inline with Hydra; abbreviated numeric formatting                    |
| `pm_chimera_diff` | Chimera                            | Current difficulty                                                   |
| `pm_chimera_clash`| Avg Chimera Clash                  | Inline with Chimera; abbreviated numeric formatting                  |
| `pm_siege`        | Siege participation                | Always rendered                                                      |
| `pm_siege_detail` | Siege setup                        | Hidden when `pm_siege` is empty/“no”/“none”                          |
| `pm_cvc`          | CvC priority                       | Uses shared CvC mapping where numeric                                |
| `pm_cvc_points`   | Minimum CvC points                 | Abbreviated number formatting                                       |
| `pm_move_urgency` | Move urgency                       | “Urgent / timing flexible” etc.                                      |
| `pm_move_date`    | Desired move window / date         | Free-text date or window                                             |
| `pm_move_reason`  | Reason for move                    | Short free-text; truncated at ~200 chars                             |
| `pm_notes`        | Anything else we should know       | Optional free-text, truncated at ~200–300 chars                      |

### Sections & layout

1. **Player & current placement**
   - `pm_ign`  
   - `pm_power` + `pm_level_detail` (inline)  
   - `pm_playstyle`  
   - `pm_current_clan`  
   - `pm_clan_type` (“What kind of clan are we looking for?”)

2. **Performance snapshot**
   - `pm_CB`  
   - `pm_hydra_diff` + `pm_hydra_clash` (inline)  
   - `pm_chimera_diff` + `pm_chimera_clash` (inline)

3. **War modes**
   - `pm_siege`  
   - `pm_siege_detail` (conditional)  
   - `pm_cvc` + `pm_cvc_points` (inline)

4. **Move intent & notes**
   - `pm_move_urgency`  
   - `pm_move_date`  
   - `pm_move_reason`  
   - `pm_notes`

### Inline formatting examples (`promo.m`)

- `Power: 8.4 M • Bracket: Midgame`
- `Hydra: Hard • Avg Hydra Clash: 450 K`
- `Chimera: Normal • Avg Chimera Clash: 310 K`
- `CvC priority: Medium • Minimum CvC points: 50 K`
- `Move urgency: Timing flexible • Target window: After next CvC`

---

## `promo.l` — Leadership-initiated move requests

This flow is filled in by **leaders** on behalf of a member. It emphasises who is being moved, who is requesting it, and why.

### Field mapping (gid → display label)

> gid names follow the `pl_…` pattern. Exact IDs should be matched to the Leadership promo sheet tab.

| gid                | Label                               | Notes                                                                 |
| ------------------ | ----------------------------------- | --------------------------------------------------------------------- |
| `pl_player_name`   | Player                              | Player being moved (Discord name / IGN)                              |
| `pl_reporter`      | Requesting leader                   | Leader filling out the request                                       |
| `pl_current_clan`  | Current clan                        | Where the player is now                                              |
| `pl_target_clan`   | Target clan / bracket               | If a specific clan is requested; otherwise desired bracket           |
| `pl_power`         | Power                               | Abbreviated number formatting                                       |
| `pl_level_detail`  | Bracket                             | Inline with Power                                                    |
| `pl_playstyle`     | Playstyle                           |                                                                       |
| `pl_CB`            | Clan Boss (one-key top chest)       | Current CB performance                                               |
| `pl_hydra_diff`    | Hydra                               | Current difficulty                                                   |
| `pl_hydra_clash`   | Avg Hydra Clash                     | Inline with Hydra; abbreviated numeric formatting                    |
| `pl_chimera_diff`  | Chimera                             | Current difficulty                                                   |
| `pl_chimera_clash` | Avg Chimera Clash                   | Inline with Chimera; abbreviated numeric formatting                  |
| `pl_siege`         | Siege participation                 | Always rendered                                                      |
| `pl_siege_detail`  | Siege setup                         | Hidden when `pl_siege` is empty/“no”/“none”                          |
| `pl_cvc`           | CvC priority                        | Uses shared CvC mapping where numeric                                |
| `pl_cvc_points`    | Minimum CvC points                  | Abbreviated number formatting                                       |
| `pl_move_reason`   | Reason for move                     | Core rationale; truncated at ~200–300 chars                          |
| `pl_move_urgency`  | Move urgency                        | “Urgent / timing flexible” etc.                                      |
| `pl_move_window`   | Suggested move window / constraints | e.g. “After Hydra reset”, “Between CvC events”                       |
| `pl_notes`         | Anything else we should know        | Optional free-text, truncated at ~200–300 chars                      |

### Sections & layout

1. **Player & reporter**
   - `pl_player_name`  
   - `pl_reporter`  
   - `pl_current_clan`  
   - `pl_target_clan` (if specified)

2. **Performance snapshot**
   - `pl_power` + `pl_level_detail` (inline)  
   - `pl_playstyle`  
   - `pl_CB`  
   - `pl_hydra_diff` + `pl_hydra_clash` (inline)  
   - `pl_chimera_diff` + `pl_chimera_clash` (inline)

3. **War modes**
   - `pl_siege`  
   - `pl_siege_detail` (conditional)  
   - `pl_cvc` + `pl_cvc_points` (inline)

4. **Move rationale & constraints**
   - `pl_move_reason`  
   - `pl_move_urgency`  
   - `pl_move_window`  
   - `pl_notes`

### Inline formatting examples (`promo.l`)

- `Power & level: 12.6 K — Endgame`
- `Hydra: Nightmare • Avg Hydra Clash: 12.6 K`
- `Chimera: Hard • Avg Chimera Clash: 1.2 M`
- `CvC: High • Avg CvC points: 120 K`

---

## Fallback & failure handling

- On any exception in summary construction, the bot posts a **fallback promo summary embed**:
  - Generic promo title and description:
    - Title: `🔥 C1C • Promo request received` (or flow-specific variants already used)
    - Description: short guidance text (“Got your request! A coordinator will review your move…”) 
  - Body text: “Promo summary unavailable — please ping @RecruitmentCoordinator”
- The failing exception is logged with:
  - Flow id (`promo.r`, `promo.m`, `promo.l`)
  - Thread / ticket code
  - Schema hash (expected vs received)
  - Error text

---

Doc last updated: 2025-11-29 (v0.9.7)
