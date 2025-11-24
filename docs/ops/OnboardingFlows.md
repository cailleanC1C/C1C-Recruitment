# Onboarding Flows

Onboarding dialogs are driven by the `ONBOARDING_TAB` worksheet. Each row in that
sheet must declare a `flow` value to associate the question with a specific
onboarding dialog.

## Flow keys

The following flow keys are recognised by the bot and must be used exactly as
written in the `flow` column:

- `welcome`
- `promo.r` – Returning Player (R####)
- `promo.m` – Member / Player Move Request (M####)
- `promo.l` – Leadership Move Request (L####)

Flow names are opaque strings; dotted names (e.g., `promo.m`) are treated as
literal values. The bot compares the `flow` column directly to these strings
when loading questions and computing schema hashes.

Doc last updated: 2025-11-24 (v0.9.7)
