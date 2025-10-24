## Environment
- `BOT_TAG`: `rec`
- `COREOPS_ENABLE_TAGGED_ALIASES`: `1`
- `COREOPS_ENABLE_GENERIC_ALIASES`: `0`
- `COREOPS_ADMIN_BANG_ALLOWLIST` size: `9`

## Registered CoreOps Commands
| Command | Category | Aliases | RBAC | Source |
| --- | --- | --- | --- | --- |
| `rec` | user | — | none | `c1c_coreops.cog` |
| `rec checksheet` | staff | — | ops_only | `c1c_coreops.cog` |
| `rec config` | staff | — | ops_only | `c1c_coreops.cog` |
| `rec digest` | staff | — | ops_only | `c1c_coreops.cog` |
| `rec env` | admin | — | admin_only | `c1c_coreops.cog` |
| `rec health` | admin | — | ops_only | `c1c_coreops.cog` |
| `rec help` | user | — | none | `c1c_coreops.cog` |
| `rec ping` | user | — | none | `c1c_coreops.cog` |
| `rec refresh` | admin | — | ops_only | `c1c_coreops.cog` |
| `rec refresh all` | admin | — | ops_only | `c1c_coreops.cog` |
| `rec refresh clansinfo` | staff | — | ops_only | `c1c_coreops.cog` |
| `rec reload` | admin | — | ops_only | `c1c_coreops.cog` |

## Help Rendered Admin Lines
| Line |
| --- |
| • `!rec env` — Shows environment info for this bot. |
| • `!rec health` — Checks the bot’s internal health status. |
| • `!rec refresh` — Refreshes a single data bucket from Google Sheets. |
| • `!rec refresh all` — Reloads all data from Sheets. |
| • `!rec reload` — Reloads runtime configs and command modules. |

## Missing Aliases
```diff
- expected_bare_set - rendered_bare_set: !checksheet, !config, !digest, !env, !health, !ping, !refresh, !refresh all, !reload
- expected_tagged_set - rendered_tagged_set: !rec checksheet, !rec config, !rec digest, !rec ping
```

## Root Cause
CoreOps only lists aliases that survive `CoreOpsCog._apply_generic_alias_policy` (source: packages/c1c-coreops/src/c1c_coreops/cog.py:919). With `COREOPS_ENABLE_GENERIC_ALIASES=0` (disabled), bare admin commands are removed from `__cog_commands__`, so the help builder never sees `!env`, `!config`, and peers. Tagged variants remain because the `rec` group stays registered while ping’s generic command persists outside the admin gate (see packages/c1c-coreops/src/c1c_coreops/cog.py:942).
