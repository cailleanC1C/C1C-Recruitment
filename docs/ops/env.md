# Environment Variable Quick Reference

This page captures the minimal environment surface needed to run the unified bot.
It complements [`docs/ops/Config.md`](Config.md) by highlighting the must-have keys
and the removal of legacy identifiers.

## Required keys

The bot will refuse to start unless all of the following keys are populated:

- `DISCORD_TOKEN`
- `GSPREAD_CREDENTIALS`
- `RECRUITMENT_SHEET_ID`
- `ONBOARDING_SHEET_ID`

All four values must be present in `.env.example` and production deployments. The
sheet identifiers are distinct: one workbook powers recruitment flows, the other
serves onboarding config and ticket tabs. Treat them as separate credentials when
managing access or rotating service accounts.

## Legacy keys removed

Older deployments referenced generic sheet identifiers such as `GOOGLE_SHEET_ID`
(or the shorter `GSHEET_ID`). These aliases are no longer read anywhere in the
codebase. Setting them has no effect and may hide misconfigurations. Always use
the explicit `*_SHEET_ID` variables documented above.

Doc last updated: 2025-11-08 (v0.9.7)
