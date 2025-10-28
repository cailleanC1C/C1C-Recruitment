# Command Metadata Audit

## Summary
- Total commands discovered: 36
- Commands missing access_tier: 1
- Commands missing function_group: 3
- Commands missing both: 1

## Findings
| Command | File:Line | access_tier | function_group | Notes |
| --- | --- | --- | --- | --- |
| ops | packages/c1c-coreops/src/c1c_coreops/cog.py:1089 | user | operational | |
| ops health | packages/c1c-coreops/src/c1c_coreops/cog.py:1346 | admin | operational | |
| health | packages/c1c-coreops/src/c1c_coreops/cog.py:1352 | admin | operational | |
| ops checksheet | packages/c1c-coreops/src/c1c_coreops/cog.py:1913 | admin | operational | |
| checksheet | packages/c1c-coreops/src/c1c_coreops/cog.py:1920 | admin | operational | |
| ops digest | packages/c1c-coreops/src/c1c_coreops/cog.py:2036 | staff | operational | |
| digest | packages/c1c-coreops/src/c1c_coreops/cog.py:2042 | admin | operational | |
| ops env | packages/c1c-coreops/src/c1c_coreops/cog.py:2087 | admin | operational | |
| env | packages/c1c-coreops/src/c1c_coreops/cog.py:2094 | admin | operational | |
| ops help | packages/c1c-coreops/src/c1c_coreops/cog.py:2101 | user | operational | |
| ops ping | packages/c1c-coreops/src/c1c_coreops/cog.py:2113 | user | operational | |
| ops config | packages/c1c-coreops/src/c1c_coreops/cog.py:2316 | admin | operational | |
| config | packages/c1c-coreops/src/c1c_coreops/cog.py:2323 | admin | operational | |
| reload | packages/c1c-coreops/src/c1c_coreops/cog.py:2343 | admin | operational | |
| ops reload | packages/c1c-coreops/src/c1c_coreops/cog.py:2358 | admin | operational | |
| refresh | packages/c1c-coreops/src/c1c_coreops/cog.py:2372 | admin | operational | |
| ops refresh | packages/c1c-coreops/src/c1c_coreops/cog.py:2387 | admin | operational | |
| refresh all | packages/c1c-coreops/src/c1c_coreops/cog.py:2454 | admin | operational | |
| ops refresh all | packages/c1c-coreops/src/c1c_coreops/cog.py:2465 | admin | operational | |
| refresh clansinfo | packages/c1c-coreops/src/c1c_coreops/cog.py:2576 | admin | operational | |
| ops refresh clansinfo | packages/c1c-coreops/src/c1c_coreops/cog.py:2586 | staff | operational | |
| clan | cogs/recruitment_clan_profile.py:65 | user | recruitment | |
| clansearch | cogs/recruitment_member.py:20 | user | recruitment | |
| clanmatch | cogs/recruitment_recruiter.py:214 | staff | recruitment | |
| ping | cogs/app_admin.py:23 | admin | operational | |
| report | cogs/recruitment_reporting.py:27 | admin | operational | |
| welcome | cogs/recruitment_welcome.py:41 | staff | recruitment | |
| welcome-refresh | cogs/recruitment_welcome.py:56 | admin | operational | |
| perm | modules/ops/permissions_sync.py:932 | admin | MISSING | Group entry lacks help metadata. |
| perm bot | modules/ops/permissions_sync.py:941 | admin | MISSING | Sub-group entry lacks help metadata. |
| perm bot list | modules/ops/permissions_sync.py:956 | admin | operational | |
| perm bot allow | modules/ops/permissions_sync.py:1034 | admin | operational | |
| perm bot deny | modules/ops/permissions_sync.py:1087 | admin | operational | |
| perm bot remove | modules/ops/permissions_sync.py:1140 | admin | operational | |
| perm bot sync | modules/ops/permissions_sync.py:1173 | admin | operational | |
| reload | packages/c1c-coreops/src/c1c_coreops/commands/reload.py:64 | MISSING | MISSING | Standalone reload command lacks tier and help metadata. |

## Hotspots
### Files
- modules/ops/permissions_sync.py — 2 command(s) missing metadata
- packages/c1c-coreops/src/c1c_coreops/commands/reload.py — 1 command(s) missing metadata

### Directories
- modules/ops — 2 command(s) missing metadata
- packages/c1c-coreops/src/c1c_coreops/commands — 1 command(s) missing metadata

## Suggested fixes
- Extend `help_metadata(...)` coverage to hidden admin aliases (e.g., `health`, `checksheet`, `digest`, `env`, `config`, `reload`, `refresh` variants) to surface consistent function groups.
- Consider applying a lightweight `help_metadata` decorator (or equivalent helper) to group roots like `perm` and `permbot` so the help system can classify them.
- Add a tier/helper decorator to `packages/c1c-coreops/src/c1c_coreops/commands/reload.py` if the command remains active so it inherits access tier and function group metadata.

Doc last updated: 2025-10-28 (v0.9.6)
