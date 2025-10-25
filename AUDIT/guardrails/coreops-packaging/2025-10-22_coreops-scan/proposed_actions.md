# Proposed Actions for `shared/*coreops*`

## shared/coreops_cog.py
- Recommendation: **Add to `c1c_coreops` → Migrate**
  - Rationale: Hosts the production CoreOps Cog (`CoreOpsCog`) and the `resolve_ops_log_channel_id` helper used by cache scheduler jobs. Keeping it in `shared/` makes extension packaging harder and couples scheduler utilities to legacy paths.
  - Missing symbols to introduce inside `c1c_coreops`: `CoreOpsCog`, `resolve_ops_log_channel_id`.
  - Proposed destination: `packages/c1c-coreops/src/c1c_coreops/cog.py` (Cog) with helper retained in the same module or a sibling `runtime.py`.
- Import rewrite plan once the package exists:
  - `modules/coreops/cog.py` — `from shared.coreops_cog import CoreOpsCog` → `from c1c_coreops.cog import CoreOpsCog`
  - `shared/sheets/cache_scheduler.py` — `from shared.coreops_cog import resolve_ops_log_channel_id` → `from c1c_coreops.cog import resolve_ops_log_channel_id`

## shared/coreops_rbac.py
- Recommendation: **Add to `c1c_coreops` → Migrate**
  - Rationale: Centralizes RBAC checks (`admin_only`, `ops_only`, `is_staff_member`, etc.) that gate commands across the bot. Relocating them alongside the CoreOps package removes the remaining `shared` dependency from recruitment and app entrypoints.
  - Missing symbols to introduce inside `c1c_coreops`: `admin_only`, `can_view_admin`, `can_view_staff`, `get_admin_role_ids`, `get_lead_role_ids`, `get_recruiter_role_ids`, `get_staff_role_ids`, `guild_only_denied_msg`, `is_admin_member`, `is_lead`, `is_recruiter`, `is_staff_member`, `ops_gate`, `ops_only`.
  - Proposed destination: `packages/c1c-coreops/src/c1c_coreops/rbac.py` (exports) with internal helpers preserved as privates.
- Import rewrite plan once available:
  - `app.py` — absolute import rewritten to `from c1c_coreops.rbac import ...`
  - `cogs/recruitment_recruiter.py` — `from c1c_coreops.rbac import is_admin_member, is_recruiter`
  - `modules/recruitment/services/search.py` — `from c1c_coreops.rbac import is_lead, is_recruiter`
  - `modules/recruitment/welcome.py` — `from c1c_coreops.rbac import is_staff_member, is_admin_member`

## shared/coreops_render.py
- Recommendation: **Add to `c1c_coreops` → Migrate**
  - Rationale: Provides dataclasses and embed builders powering CoreOps diagnostics (`build_config_embed`, `build_refresh_embed`, etc.). Migrating keeps render primitives with the Cog package and cuts the last `shared` dependency from runtime bootstrap.
  - Missing symbols to introduce inside `c1c_coreops`: dataclasses `ChecksheetEmbedData`, `ChecksheetSheetEntry`, `ChecksheetTabEntry`, `DigestEmbedData`, `DigestSheetEntry`, `DigestSheetsClientSummary`, `RefreshEmbedRow`; functions `build_checksheet_tabs_embed`, `build_config_embed`, `build_digest_embed`, `build_digest_line`, `build_env_embed`, `build_health_embed`, `build_refresh_embed`.
  - Proposed destination: `packages/c1c-coreops/src/c1c_coreops/render.py` (dataclasses + embed builders).
- Import rewrite plan once exported:
  - `modules/common/runtime.py` — `from c1c_coreops.render import build_refresh_embed, RefreshEmbedRow`
  - `shared/coreops_cog.py` (post-migration) — adjust internal import to the new module (e.g., `from c1c_coreops.render import ...`).

## shared/coreops_prefix.py
- Recommendation: **Add to `c1c_coreops` → Migrate**
  - Rationale: Exposes the admin prefix detector used at startup. Moving it alongside the CoreOps RBAC/helpers keeps all command gating primitives under the dedicated package.
  - Missing symbols to introduce inside `c1c_coreops`: `detect_admin_bang_command` (plus supporting `_normalize_commands` kept private).
  - Proposed destination: `packages/c1c-coreops/src/c1c_coreops/prefix.py`.
- Import rewrite plan once exported:
  - `app.py` — `from c1c_coreops.prefix import detect_admin_bang_command`

Doc last updated: 2025-10-22 (v0.9.5)
