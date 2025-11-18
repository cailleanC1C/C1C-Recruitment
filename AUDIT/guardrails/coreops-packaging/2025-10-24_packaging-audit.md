# CoreOps Packaging Audit

Generated: 2025-10-24T10:15:26Z
Commit: unknown
Total files scanned: 129
Result: **FAIL** (22 offenses)

## Docs/Config Drift

| Path | Line | Snippet |
| --- | --- | --- |
| `CHANGELOG.md` | 18 | `* Consolidate CoreOps to `modules/coreops`; remove `shared/coreops`.` |
| `docs/adr/ADR-0002-cache-telemetry-wrapper.md` | 13 | `- Introduce `shared/coreops/cache_public.py` as the only import surface for telemetry.` |
| `docs/guardrails/RepositoryGuardrails.md` | 25 | `- **C-09 No Legacy Paths:** No imports from removed legacy paths (e.g., top-level `recruitment/`, `shared/coreops`, `shared/utils/coreops_*`).` |
| `docs/modules/CoreOps-Development.md` | 4 | `- Import telemetry data via `shared.coreops.cache_public` helpers (`list_buckets`,` |

## Duplicate CoreOps Symbols

| Path | Line | Snippet |
| --- | --- | --- |
| `shared/help.py` | 269 | `def build_help_overview_embed(` |
| `shared/help.py` | 297 | `def build_help_detail_embed(` |

## Shim/Re-export Bridges

| Path | Line | Snippet |
| --- | --- | --- |
| `shared/coreops_cog.py` | 13 | `from c1c_coreops.cog import *  # noqa: F401,F403` |
| `shared/coreops_prefix.py` | 13 | `from c1c_coreops.prefix import *  # noqa: F401,F403` |
| `shared/coreops_rbac.py` | 13 | `from c1c_coreops.rbac import *  # noqa: F401,F403` |
| `shared/coreops_render.py` | 13 | `from c1c_coreops.render import *  # noqa: F401,F403` |

## Stray CoreOps Paths

| Path | Line | Snippet |
| --- | --- | --- |
| `modules/coreops/__init__.py` | - | `Path contains coreops outside package` |
| `modules/coreops/cog.py` | - | `Path contains coreops outside package` |
| `modules/coreops/cron_summary.py` | - | `Path contains coreops outside package` |
| `modules/coreops/cronlog.py` | - | `Path contains coreops outside package` |
| `modules/coreops/helpers.py` | - | `Path contains coreops outside package` |
| `modules/coreops/ops.py` | - | `Path contains coreops outside package` |
| `shared/coreops_cog.py` | - | `Path contains coreops outside package` |
| `shared/coreops_prefix.py` | - | `Path contains coreops outside package` |
| `shared/coreops_rbac.py` | - | `Path contains coreops outside package` |
| `shared/coreops_render.py` | - | `Path contains coreops outside package` |
| `tests/test_coreops_basic.py` | - | `Path contains coreops outside package` |
| `tests/test_coreops_imports.py` | - | `Path contains coreops outside package` |

## Fix-It Checklist

- Rewrite imports to use `c1c_coreops.*` directly.
- Move or delete stray CoreOps files outside `packages/c1c-coreops`.
- Remove shim files in `shared/` that re-export from `c1c_coreops`.
- Delete duplicate CoreOps symbol definitions outside the package.
- Update docs/configs to reference `c1c_coreops` paths only.

Doc last updated: 2025-11-17 (v0.9.7)
