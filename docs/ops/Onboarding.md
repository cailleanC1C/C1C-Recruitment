# Onboarding

## Config keys
| Key | Source | Notes |
| --- | --- | --- |
| `ONBOARDING_SHEET_ID` | Environment | Sheet identifier for the onboarding workbook (separate from recruitment). |
| `ONBOARDING_TAB` | Onboarding Config sheet | Tab name for the onboarding questions worksheet. Preloaded at startup and refreshed weekly; required headers: `flow, order, qid, label, type, required, maxlen, validate, help, note, rules`. |

## Notes
- The onboarding questions cache preloads during startup alongside `clans`, `templates`, and `clan_tags`.
- A scheduled refresh runs weekly via the cache scheduler (`interval=7d`).
- The onboarding sheet ID resolves strictly from `ONBOARDING_SHEET_ID`; legacy fallbacks are disabled.

## Troubleshooting
- `missing config key: ONBOARDING_TAB` — Sheet configuration does not provide the tab name. Update the Config sheet and rerun the refresh. (Alias `onboarding.questions_tab` is no longer accepted.)
- `onboarding_questions cache is empty (should be preloaded)` — Startup preload failed or returned zero rows. Fix the sheet and rerun the cache refresh (`!ops refresh onboarding_questions`).

## Lifecycle & Single-Message Policy

The onboarding wizard lives in **one panel message** inside the ticket thread.
All user-visible updates **edit that same message**. The wizard does not post
additional messages for state changes.

Component handlers use a single acknowledgment path (`defer_update`) and route
through one controller render pipeline to avoid duplicate edits or red toasts.

Persistent views for the onboarding UI are **registered after the bot is ready**
so components remain active across restarts.

Doc last updated: 2025-11-07 (v0.9.7)
