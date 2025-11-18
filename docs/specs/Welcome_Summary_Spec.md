# Welcome Summary Embed — Readability Spec (v2.1)

## Overview
- Recruitment summary embeds now source display ordering and labels from the Welcome sheet `gid` values.
- No schema changes are required; all fields reuse the existing onboarding questionnaire columns.
- The embed honours the sheet-driven visibility rules (skip/optional decisions) resolved during the welcome flow.
- Inline formatting keeps Hydra and Chimera clash averages alongside their difficulty answers.
- Labels render in bold for easier scanning, including inline pairs.

> **Style reference:** General embed, panel, and help formatting lives in
> [`docs/_meta/DocStyle.md`](../_meta/DocStyle.md). This spec only defines the
> Welcome summary’s field order and hide logic.

## Field mapping (gid → display label)
| gid | Label | Notes |
| --- | ----- | ----- |
| `w_ign` | Ingame Name |  |
| `w_power` | Power | Inline with `w_level_detail`; abbreviated number formatting |
| `w_level_detail` | Bracket | Single-select label from question 4b |
| `w_playstyle` | Playstyle |  |
| `w_clan` | Looking for |  |
| `w_CB` | Clan Boss (one-key top chest) |  |
| `w_hydra_diff` | Hydra |  |
| `w_hydra_clash` | Avg Hydra Clash | Inline with `w_hydra_diff`; abbreviated number formatting |
| `w_chimera_diff` | Chimera |  |
| `w_chimera_clash` | Avg Chimera Clash | Inline with `w_chimera_diff`; abbreviated number formatting |
| `w_siege` | Siege participation | Always rendered |
| `w_siege_detail` | Siege setup | Hidden when Siege participation is empty/"no"/"none" |
| `w_cvc` | CvC priority | Mapped 1–5 → Low…High |
| `w_cvc_points` | Minimum CvC points | Abbreviated number formatting |
| `w_level` | Progression (self-feel) | Optional; truncated at 200 characters |
| `w_origin` | Heard about C1C from |  |

## Sections & layout
1. **Identity & intent** — `w_ign`, `w_power` + `w_level_detail`, `w_playstyle`, `w_clan`
2. **Progress & bossing** — `w_CB`, `w_hydra_diff` + `w_hydra_clash`, `w_chimera_diff` + `w_chimera_clash`
3. **War modes** — `w_siege`, `w_siege_detail`, `w_cvc` + `w_cvc_points`
4. **Notes** — `w_level` (optional), `w_origin`

Inline pairs are rendered with a mid-dot separator (`•`) to keep paired answers on a single line. Each sub-label stays bold for readability:
- `**Power:** … • **Bracket:** …`
- `**Hydra:** … • **Avg Hydra Clash:** …`
- `**Chimera:** … • **Avg Chimera Clash:** …`
- `**CvC priority:** … • **Minimum CvC points:** …`

## Hide rules
- Skip any field whose rendered value is empty or matches `0`, `no`, `none`, or `dunno` (case-insensitive).
- `w_siege` is the exception and always appears, even when the answer is "No".
- `w_siege_detail` is hidden when Siege participation resolves to an empty/"no"/"none" value.

## Number formatting
- `w_power`, `w_hydra_clash`, `w_chimera_clash`, and `w_cvc_points` display as `### K` or `#.# M` (one decimal max).
- Values below 1,000 remain unmodified.

## CvC priority mapping
| Sheet value | Display |
| ----------- | ------- |
| `1` | Low |
| `2` | Low-Medium |
| `3` | Medium |
| `4` | High-Medium |
| `5` | High |

## Visibility and failure handling
- Only answers with a resolved visibility state other than `skip` are rendered.
- If summary generation fails, a fallback embed is posted with the message “Summary unavailable — see logs”.

## Sample render
```
🔥 C1C • Recruitment Summary
Keep this thread open until a recruiter confirms placement.

**Ingame Name:** C1C Caillean
**Power:** 12.6 M • **Bracket:** Beginner
**Playstyle:** Competitive
**Looking for:** Active, social clan with Hydra focus

🧩 Progress & Bossing
**Clan Boss (one-key top chest):** Normal
**Hydra:** Normal • **Avg Hydra Clash:** 320 K
**Chimera:** Easy • **Avg Chimera Clash:** 240 K

⚔️ War Modes
**Siege participation:** No
**CvC priority:** High-Medium • **Minimum CvC points:** 60 K

🧭 Notes
**Progression (self-feel):** Late-game damage dealer refining Hydra teams.
**Heard about C1C from:** A friend in global chat
```

Doc last updated: 2025-11-17 (v0.9.7)
