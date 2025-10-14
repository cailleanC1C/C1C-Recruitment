# Phase 2 Review Notes

## Harmonization outcome
- Migrated to single Discord bot process with modular cogs for recruitment and onboarding.
- Shared CoreOps command set across environments; admins rely on `!help`, `!ping`, `!health`, `!reload` only.
- Guild access now enforced via unified `GUILD_IDS` allow-list on startup.

## Environment keys
- Removed duplicate singular keys (`*_ROLE_ID`) in favor of plural list variants.
- `.env.dev`, `.env.test`, `.env.prod` now share the exact same key names, simplifying promotion.

## Documentation
- README and config docs updated to reflect single-bot architecture and Config tab requirements.
- CoreOps doc aligned with the consolidated command surface and logging policy.

No regressions observed during dry-run; watchdog cadence validated in dev and test.
