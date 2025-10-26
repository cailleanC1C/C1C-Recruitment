# Module Toggles

The FeatureToggles worksheet (see `docs/ops/Config.md`) governs which modules load
at startup. Toggle values are case-insensitive; only `TRUE` (`ON`) enables a feature.

## Recruitment

| Toggle | Default | Notes |
| --- | --- | --- |
| `member_panel` | `TRUE` | Enables prefix `!clansearch` for members (single-message results updated in-place). |
| `recruiter_panel` | `ON` | Enables the text-only recruiter panel (`!clanmatch`). |
| `clan_profile` | `ON` | Enables the public `!clan` command with crest and 💡 reaction toggle. |
| `recruitment_welcome` | `TRUE` | Enables the `!welcome` command; onboarding listeners remain env-gated. |
| `recruitment_reports` | `TRUE` | Enables the Daily Recruiter Update (UTC scheduler + `!report recruiters`). |

## Placement

| Toggle | Default | Notes |
| --- | --- | --- |
| `placement_target_select` | `TRUE` | Stub module for future placement picker. |
| `placement_reservations` | `TRUE` | Stub module for future reservation workflow. |

Set the desired value in the `FeatureToggles` tab, then run `!rec refresh config`
to apply it. The runtime logs whether each module was loaded or skipped at boot. See
[`Config.md`](Config.md#feature-toggles-worksheet) for the worksheet contract.

Doc last updated: 2025-10-26 (v0.9.6)
