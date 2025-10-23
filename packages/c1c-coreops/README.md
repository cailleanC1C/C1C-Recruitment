# c1c-coreops

Internal-only bundle of the CoreOps cog, RBAC helpers, embed renderers, and
prefix detection utilities shared across C1C bots.

## Contents
- `c1c_coreops.cog` — CoreOps command handlers, telemetry views, and embeds.
- `c1c_coreops.rbac` — Role gating checks aligned with the recruitment runtime.
- `c1c_coreops.render` — Embed dataclasses and formatting helpers for digests.
- `c1c_coreops.prefix` — Bang-command detection for admin shortcuts.

Legacy modules continue to re-export these symbols from `shared/coreops_*` for
one release so downstream importers have time to migrate.
