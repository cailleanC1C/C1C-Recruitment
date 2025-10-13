# CoreOps RBAC & Prefix Override – Phase 1 Notes

## Summary
- Replaced the user-ID gate with role-aware checks that read `ADMIN_ROLE_ID` (single role) and `STAFF_ROLE_IDS` (comma/space separated roles) via `shared/coreops_rbac.py`.
- Updated the CoreOps commands to reuse the shared staff predicate, replying with the legacy "Staff only" denial string without any prefix hint.
- Added an admin-only, prefixless CoreOps passthrough that rewrites qualifying messages before they reach the dispatcher, matching the historical override used in the legacy bots.
- Refreshed the CoreOps help footer so it keeps the live Vienna/UTC timestamp alongside the existing version string.

## Environment keys
- `ADMIN_ROLE_ID`: numeric Discord role ID for the CoreOps admin override. Treated as optional; ignored if unset or malformed.
- `STAFF_ROLE_IDS`: comma/space separated numeric Discord role IDs that qualify for staff access. Empty/malformed entries are ignored.

## Implementation details
- `shared/coreops_rbac.py` parses the environment values once, filters out non-numeric tokens, and exposes `is_staff_member` / `is_admin_member` helpers for both the cog and the prefix bridge.
- `modules/coreops/cog.py` swaps the decorator to the shared helper and removes the prefix hint embed on denial.
- `app.py` calls `maybe_admin_coreops_message(...)` before the regular dispatcher. When an admin types `health`, `env`, `digest`, or `help` with no prefix, the synthetic message is sent through with the configured prefix injected (`rec health`, etc.).
- `shared/help.py` continues to show the same command layout but now prints `Bot v{BOT_VERSION} • CoreOps v1.0.0 • 2025-10-13 09:17 Europe/Vienna` (example) by reusing the Vienna/UTC helper.

## Usage examples
- Admin with `ADMIN_ROLE_ID=123` can type `health`, `!rec health`, or mention-prefix variants; all resolve identically.
- Staff member with a role in `STAFF_ROLE_IDS=456,789` can run `!rec env` but receives “Staff only” when that role is removed.
- Non-staff typing `health` or `!rec health` receives the “Staff only” reply with no additional hints.
