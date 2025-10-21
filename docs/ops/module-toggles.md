# Module toggles — Phase 5

The FeatureToggles worksheet (see `docs/ops/Config.md`) governs which modules load
at startup. Toggle values are case-insensitive; only `TRUE` enables a feature.

## Recruitment

| Toggle | Default | Notes |
| --- | --- | --- |
| `member_panel` | `TRUE` | Enables member-facing search flows (future `!clansearch`). |
| `recruiter_panel` | `TRUE` | Loads the recruiter-only `!clanmatch` panel. |
| `clan_profile` | `FALSE` | Enables the public `!clan <tag>` command (in-channel crest card with 💡 reaction flip). |
| `recruitment_welcome` | `TRUE` | Welcome command and onboarding listeners. |
| `recruitment_reports` | `TRUE` | Daily recruiter digest embed. |

## Placement

| Toggle | Default | Notes |
| --- | --- | --- |
| `placement_target_select` | `TRUE` | Enables placement target picker inside recruiter workflows. |
| `placement_reservations` | `TRUE` | Reservation holds and release workflow. |

Set the desired value in the `FeatureToggles` tab, then run `!rec refresh config`
to apply it. The runtime logs whether each module was loaded or skipped at boot.
