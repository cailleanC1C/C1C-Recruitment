# Onboarding

## Config keys
| Key | Source | Notes |
| --- | --- | --- |
| `ONBOARDING_SHEET_ID` | Environment | Sheet identifier for the onboarding workbook (separate from recruitment). |
| `ONBOARDING_TAB` | Onboarding Config sheet | Tab name for the onboarding questions worksheet. Preloaded at startup and refreshed weekly; required headers: `flow, order, qid, label, type, required, maxlen, validate, help, note, rules`. |

## Notes
- The onboarding questions cache preloads during startup alongside `clans`, `templates`, and `clan_tags`.
- A scheduled refresh runs weekly via the cache scheduler (`interval=7d`).

## Troubleshooting
- `missing config key: ONBOARDING_TAB` — Sheet configuration does not provide the tab name. Update the Config sheet and rerun the refresh. (Alias `onboarding.questions_tab` is no longer accepted.)
- `onboarding_questions cache is empty (should be preloaded)` — Startup preload failed or returned zero rows. Fix the sheet and rerun the cache refresh (`!ops refresh onboarding_questions`).

Doc last updated: 2025-11-07 (v0.9.7)
