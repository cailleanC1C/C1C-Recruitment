# Contributing Guide (Phase 3)

Thanks for helping improve the C1C Recruitment bot! This guide covers the contribution
workflow and the new command tiering requirements introduced in PR4.

## Workflow
1. Open an issue or link to a task that describes the change.
2. Branch from `main` and follow our commit conventions.
3. Keep docs in sync with behavior changes. Update relevant files under `docs/`.
4. Run the applicable tests or smoke checks locally before opening a PR.
5. Every PR must include metadata in the body:
   ```
   [meta]
   labels: docs, devx, comp:ops-contract, P2
   milestone: Harmonize v1.0
   [/meta]
   ```

## Adding new commands
Follow this checklist to integrate cleanly with the tiered help system. See the
[Command System Guide](commands.md#adding-new-commands-developer-guide) for code snippets.

1. **Register the command** with `@commands.command()` or inside an existing group such as
   `@rec.command()`.
2. **Declare the tier** using `@tier("user"|"staff"|"admin")` from
   `shared.coreops.helpers.tiers`.
3. **Gate execution** with the helpers in `shared.coreops_rbac` (e.g. `is_admin_member()`,
   `is_staff_member()`) or decorators like `@ops_only("admin")`. Never rely on Discord
   permission flags such as `manage_guild`.
4. **Optional – hide from help** by setting `cmd.extras["hide_in_help"] = True` for
   internal commands.
5. **Audit tiers** locally:
   ```python
   from shared.coreops.helpers.tiers import rehydrate_tiers, audit_tiers

   rehydrate_tiers(bot)
   audit_tiers(bot, log)
   ```
   Confirm "Help tiers missing for:" is empty.
6. **Verify visibility** by running `!rec help` as user/staff roles and `!help` as admin.
7. **Document** any new command behavior in `docs/commands.md` and the CoreOps contract if
   it affects staff or admin workflows.
8. **Add PR metadata** for command work:
   ```
   [meta]
   labels: commands, comp:ops-contract, devx
   milestone: Harmonize v1.0
   [/meta]
   ```

## Code style
- Follow existing patterns; prefer composition over inheritance in cogs.
- Imports should remain grouped by standard library, third-party, and project modules.
- Avoid wrapping imports in try/except blocks.

## Communication
- Use the #c1c-platform channel for platform support.
- Flag urgent production incidents to the on-call admin with context and recent logs.

---

_Doc last updated: 2025-10-18 (PR4)_
