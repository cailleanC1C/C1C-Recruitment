# Phase 5 Audit — `!clansearch` Port Status (2025-10-25)

## Executive Summary
The new recruitment bot only preserves scaffolding for the member-facing `!clansearch` flow. The command entrypoint, runtime wiring, and shared filtering utilities never migrated from the legacy Matchmaker code, leaving the feature inaccessible despite having UI and embed components ready. Sheets adapters, emoji rendering, and configuration knobs exist, but no module currently stitches them into a user-facing command. As a result, members still cannot launch search panels, and supporting helpers remain recruiter-only or unused stubs.

Porting can proceed once we add a lightweight intake cog that mirrors the legacy command contract, refactor recruiter filtering helpers for shared use, and hook panel lifecycle management (active panel reuse, results cleanup) into the member surface. Without those pieces the experience remains dark, and documentation referencing `!clansearch` continues to mislead operators.

## Evidence Map
- **Entry & gating**
  - Placeholder cog exports no commands; setup is a no-op. `cogs/recruitment_member.py:L1-L22`
  - Runtime only loads the recruiter cog; member cog is never considered. `modules/common/runtime.py:L804-L832`
  - Feature module shim stops at `ensure_loaded` and never registers commands. `modules/recruitment/services/search.py:L1-L40`
- **Member UI scaffolding**
  - `MemberSearchPagedView` implements the member results pager with ownership checks and attachment rotation. `modules/recruitment/views/shared.py:L15-L255`
  - `SearchResultFlipView` exists but has no caller; intended for single-result flips. `modules/recruitment/views/shared.py:L259-L353`
- **Recruiter reuse targets**
  - Recruiter panel defines filtering helpers (`_row_matches`, `_format_filters_footer`, `_parse_number`) still scoped to recruiter flows. `modules/recruitment/views/recruiter_panel.py:L170-L249`
  - Search execution relies on async Sheets access and soft-cap enforcement already ported for recruiters. `modules/recruitment/views/recruiter_panel.py:L820-L938`
- **Embeds & media**
  - Card builders cover lite, entry, and profile variants with crest handling. `modules/recruitment/cards.py:L1-L178`
  - Emoji pipeline rebuilds thumbnails asynchronously and honours strict proxy flags. `modules/recruitment/emoji_pipeline.py:L1-L161`
- **Data adapters & config**
  - Recruitment Sheets accessor fetches clan matrices, caches rows, and exposes async cache loaders. `shared/sheets/recruitment.py:L1-L200`
  - Async facade wraps synchronous Sheets calls via `asyncio.to_thread`. `shared/sheets/async_facade.py:L1-L95`
  - Config exposes `SEARCH_RESULTS_SOFT_CAP`, emoji sizing, and proxy toggles required by member cards. `shared/config.py:L320-L352`
- **Feature flags & docs**
  - `member_panel` toggle documented but currently lights nothing. `docs/ops/module-toggles.md:L6-L27`
  - Command matrix lists `!clansearch` as gated, implying availability. `docs/ops/CommandMatrix.md:L25-L45`
  - Help copy already references `!rec help clansearch`. `shared/help.py:L205-L231`
- **Legacy baseline for parity**
  - Prior audit documents the expected command behavior, ownership rules, and helper inventory. `AUDIT/20251019_PHASE5/MM_clansearch_audit.md:L1-L143`

## Readiness Matrix
| Status | Items | Notes |
| --- | --- | --- |
| **Present** | `MemberSearchPagedView`, `SearchResultFlipView`, embed builders, emoji pipeline, Sheets adapters/cache, `SEARCH_RESULTS_SOFT_CAP` config, `member_panel` toggle docs | UI + data plumbing exist but are unused without an intake command. |
| **Missing** | Prefix command & cooldown, runtime cog load, active-panel registry for members, shared filtering helpers, results message lifecycle, slash-command parity, tests & help alignment | Core flow is absent; existing recruiter logic is not shared. |
| **Conflicts** | Filtering helpers marked private in recruiter module, no shared module for roster parsing, member docs advertise unavailable command, placeholder cog loaded via `modules.recruitment.services.search` without exposing functionality | Code organization prevents reuse; docs and runtime disagree on availability. |
| **Risks** | Re-sending results each toggle can spam channels without owner reuse guard, emoji thumbnail fetches rely on guild emoji permissions, Sheets fetch stays synchronous unless routed through async facade | Need guardrails before exposing to members. |

## Blockers (P0/P1)
- No command wiring: members cannot invoke any search flow (`cogs/recruitment_member.py`, `modules/common/runtime.py`).
- Filtering utilities stay recruiter-only; member path lacks shared helpers for roster logic (`modules/recruitment/views/recruiter_panel.py`).
- Active panel tracking absent; repeat summons would spawn unlimited panels without cleanup or ownership checks (`RecruiterPanelCog` equivalent missing for members).
- Documentation currently overpromises feature availability (Command Matrix, help text) without runtime support.

## Follow-ups (P2+)
- Evaluate need for slash-command mirror once prefix parity lands.
- Harden emoji pipeline error handling for member-heavy usage (rate limiting, caching attachments).
- Publish column-to-filter mapping for clan sheet tabs in operator docs.
- Backfill automated tests covering search pagination and crest attachment cleanup.

## Exact To-Do List
- **`modules/common/runtime.py`** – load the member cog under the `member_panel` flag:
  ```diff
   await _load_feature_module(
       "modules.recruitment.services.search", ("member_panel", "recruiter_panel")
   )
+  await _load_feature_module("cogs.recruitment_member", ("member_panel",))
  await _load_feature_module("cogs.recruitment_recruiter", ("recruiter_panel",))
  ```
- **`modules/recruitment/services/search.py`** – expose a setup helper that registers both recruiter and member cogs (or ensures legacy shims call into new command wiring):
  ```diff
  async def setup(bot: commands.Bot) -> None:
-    # TODO(phase3): wire recruitment search commands once Sheets access lands.
-    await ensure_loaded(bot)
+    await ensure_loaded(bot)
+    from cogs import recruitment_member
+    await recruitment_member.setup(bot)
  ```
  (Adjust once the member cog owns its own `setup`.)
- **`cogs/recruitment_member.py`** – implement the prefix command mirroring the legacy flow:
  ```py
  class RecruitmentMember(commands.Cog):
      @commands.cooldown(1, 2, commands.BucketType.user)
      @commands.command(name="clansearch")
      async def clansearch(self, ctx: commands.Context, *, extra: str | None = None) -> None:
          """Launch the member search panel (no arguments allowed)."""
          ...
  async def setup(bot: commands.Bot) -> None:
      await bot.add_cog(RecruitmentMember(bot))
  ```
  - Reject extra arguments, reuse an `ACTIVE_PANELS`-style registry, and seed the panel intro embed before handing off to a member view.
- **New shared helper module** (e.g., `modules/recruitment/search_helpers.py`) – extract reusable logic from the recruiter panel:
  ```py
  def row_matches(row, cb, hydra, chimera, cvc, siege, playstyle): ...
  def parse_spots_num(cell_text: str) -> int: ...
  def parse_inactives_num(cell_text: str) -> int: ...
  def format_filters_footer(...): ...
  ```
  - Update recruiter and member flows to consume the shared helpers to avoid divergence.
- **Member panel orchestration** – create a `MemberPanelController` (new module under `modules/recruitment/views/member_panel.py`) responsible for:
  - Hydrating filters from `ClanMatchView`-style defaults (CB/Hydra/Chimera/Playstyle toggles + roster mode).
  - Calling `sheets.fetch_clans()` via `shared.sheets.async_facade.fetch_clans()`.
  - Instantiating `MemberSearchPagedView` with embeds/files returned from new helpers.
  - Tracking and reusing prior results messages to avoid channel spam.
- **Documentation updates** – once the command ships, flip `!clansearch` status to ✅ in `docs/ops/CommandMatrix.md` and add usage notes to `docs/ops/Config.md` / `docs/ops/module-toggles.md`. Ensure `docs/ops/Config.md` references any new ENV (none anticipated beyond existing `SEARCH_RESULTS_SOFT_CAP`).
- **Testing** – add integration tests covering argument rejection, search soft-cap enforcement, and ownership checks (e.g., new tests under `tests/recruitment/test_member_panel.py`).

## Compatibility Notes
- Maintain the legacy contract: prefix-only command, 2-second per-user cooldown, no arguments accepted, and automatic reuse of an existing panel (`ACTIVE_PANELS` behavior).
- Preserve member ownership enforcement for both the panel and paginated results (`⚠️ Not your panel` / `Not your result` messaging).
- Continue respecting `SEARCH_RESULTS_SOFT_CAP`, roster mode semantics (open/full/inactives), and the lite/entry/profile embed modes with crest thumbnails.
- Keep responses in-channel (no DM dependency) and ensure invoking message deletion remains optional based on permissions.

## Observability Plan
- Emit structured logs for each invocation (`command=clansearch`, `guild_id`, `actor_id`, `filters`, `result_count`, `capped` flag) to trace usage and diagnose Sheets latency.
- Reuse cache telemetry from `shared.sheets.cache_service` by tagging member-triggered refreshes; alert when `result` is `fail` or retries exceed 0.
- Log panel lifecycle events (`panel_opened`, `panel_reused`, `panel_closed`) with message IDs to identify orphaned messages for cleanup.
- Surface emoji thumbnail failures via the existing `c1c.recruitment.emoji` logger and aggregate counts for missing crest assets.

Doc last updated: 2025-10-25 (v0.9.5)
