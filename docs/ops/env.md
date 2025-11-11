# Environment Variable Quick Reference

This page captures the minimal environment surface needed to run the unified bot.
It complements [`docs/ops/Config.md`](Config.md) by highlighting the must-have keys
and the removal of legacy identifiers.

## Required keys

The bot will refuse to start unless all of the following keys are populated:

- `DISCORD_TOKEN`
- `GSPREAD_CREDENTIALS`
- `RECRUITMENT_SHEET_ID`

These must exist in `.env.example`, local development shells, and every
deployment target. `RECRUITMENT_SHEET_ID` points at the primary workbook that
feeds recruitment commands, digests, and feature toggles.

## Onboarding-dependent keys

`ONBOARDING_SHEET_ID` is optional for startup but required for onboarding
features. When it is blank, the process still boots, yet the following degrade:

- Onboarding cache warmers raise `missing config key` errors during refresh.
- Watchers that sync welcome/promo ticket state skip their jobs.
- Any command that reads onboarding questionnaire data returns fallback copy or
  soft-errors in logs.

Populate the key to restore the full onboarding flow. Ensure onboarding-only
deployments use a dedicated service account and sheet permissions where
possible.

## Legacy keys removed

Older deployments referenced generic sheet identifiers such as
`GOOGLE_SHEET_ID` (or the shorter `GSHEET_ID`). These aliases are no longer read
anywhere in the codebase. Setting them has no effect and may hide
misconfigurations. Always use the explicit `*_SHEET_ID` variables documented
above.

Doc last updated: 2025-11-08 (v0.9.7)
