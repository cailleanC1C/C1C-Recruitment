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

## Promo ticket onboarding

Promo tickets under `PROMO_CHANNEL_ID` trigger onboarding dialogs using the
same Open Questions panel as welcome tickets:

- Ticket Tool greetings include one hidden trigger line:
  - `<!-- trigger:promo.r -->` — Returning Player
  - `<!-- trigger:promo.m -->` — Member / Player Move Request
  - `<!-- trigger:promo.l -->` — Leadership Move Request
- When the trigger is detected, the bot reacts and posts the panel starter
  message in the promo thread. Recruiters can also add 🎫 to the greeting to
  reveal the panel if the watcher missed it.
- Once the panel is opened, `start_welcome_dialog` resolves the flow key
  (`promo.r`, `promo.m`, `promo.l`) and loads the corresponding question set
  from `ONBOARDING_TAB`.

Doc last updated: 2025-11-24 (v0.9.8.2)
