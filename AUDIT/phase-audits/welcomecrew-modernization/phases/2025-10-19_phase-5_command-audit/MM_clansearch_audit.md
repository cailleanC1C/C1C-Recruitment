# Legacy Matchmaker `!clansearch` Audit — Phase 5 (2025-10-19)

This document inventories the current member-facing `!clansearch` implementation in `AUDIT/20251010_src/MM/bot_clanmatch_prefix.py` and related scaffolding. It is meant to seed wiring work; no runtime code was changed during this audit.

## 1) Command Surface & UX
- **Command(s):** Prefix-only `!clansearch` registered on the legacy `commands.Bot`. A per-user 2s cooldown is enforced and duplicate panels are prevented via the `ACTIVE_PANELS` map. The command rejects extra arguments before opening the member panel.

  ```python
  # AUDIT/20251010_src/MM/bot_clanmatch_prefix.py:L1807-L1846
  @commands.cooldown(1, 2, commands.BucketType.user)
  @bot.command(name="clansearch")
  async def clansearch_cmd(ctx: commands.Context, *, extra: str | None = None):
  # Guard: this command takes no arguments
      if extra and extra.strip():
          msg = (
              "❌ `!clansearch` doesn’t take a clan tag or name.\n"
              "• Use **`!clan <tag or name>`** to see a specific clan profile (e.g., `!clan C1CE`).\n"
              "• Or type **`!clansearch`** by itself to open the filter panel."
          )
          await ctx.reply(msg, mention_author=False)
          await _safe_delete(ctx.message)
          return

      view = ClanMatchView(author_id=ctx.author.id, embed_variant="search", spawn_cmd="search")
      view.owner_mention = ctx.author.mention
      view._sync_visuals()

      embed = discord.Embed(
          title="Search for a C1C Clan",
          description=panel_intro("search", ctx.author.mention, private=False) + "\n\n"
                      "Pick any filters *(you can leave some blank)* and click **Search Clans** "
                      "to see Entry Criteria and open Spots."
      )
      embed.set_footer(text="Only the summoner can use this panel.")

      key = (ctx.author.id, "search")
      old_id = ACTIVE_PANELS.get(key)
      if old_id:
          try:
              msg = await ctx.channel.fetch_message(old_id)
              view.message = msg
              await msg.edit(embed=embed, view=view)
              await _safe_delete(ctx.message)
              return
          except Exception:
              pass

      sent = await ctx.reply(embed=embed, view=view, mention_author=False)
      view.message = sent
      ACTIVE_PANELS[key] = sent.id
      await _safe_delete(ctx.message)
  ```

- **Arguments & options:** No user-supplied arguments allowed; failure message is posted in-channel then the invoking message is deleted. All filtering happens through the UI components on the spawned view.
- **Permissions/RBAC:** Unlike recruiter flows, no explicit role or permission gate is applied; any guild member who can execute prefix commands can open the panel. Owner-locking is enforced later via view interaction guards.
- **Embeds/Panels:** The command instantiates `ClanMatchView` with `embed_variant="search"`, yielding four dropdowns (CB, Hydra, Chimera, Playstyle) and four buttons (CvC toggle, Siege toggle, roster cycling, Reset) plus the `Search Clans` CTA. The introductory embed notes panel ownership.
- **User flows:**
  - **Success path:** On `Search Clans`, results stream to a dedicated results message with pagination + view-mode toggles (`MemberSearchPagedView`). Cards default to a “lite” overview but can flip to entry criteria or full profile without leaving the page.
  - **Validation failures:** Hitting `Search Clans` with no filters (after toggling roster to “Any” and leaving others blank) replies with `Pick at least **one** filter, then try again. 🙂`.
  - **Empty results:** `No matching clans found. You might have set too many filter criteria — try again with fewer.` is sent as a regular follow-up (visible in-channel).
  - **Too many results:** A soft cap truncates to `SEARCH_RESULTS_SOFT_CAP` rows and appends `first N of M` to the footer string.
  - **Ownership guard:** Any interaction from non-owners yields `⚠️ Not your panel. Type **!clansearch** to open your own.` as an ephemeral response.
  - **Rate limits:** Only the command-level cooldown is enforced; there is no per-panel throttling of the search button beyond Discord interaction limits.

## 2) Code Topology (Paths & Entry Points)
- **Primary module:** All member-panel behavior lives inside `AUDIT/20251010_src/MM/bot_clanmatch_prefix.py`.
- **Shared view implementation:** `ClanMatchView` powers both recruiter and member panels; the `embed_variant="search"` flag triggers member-specific result handling (attachments, alternate embeds) in the `search` handler.

  ```python
  # AUDIT/20251010_src/MM/bot_clanmatch_prefix.py:L1415-L1556 (excerpt)
  @discord.ui.button(label="Search Clans", style=discord.ButtonStyle.primary, row=4, custom_id="cm_search")
  async def search(self, itx: discord.Interaction, _btn: discord.ui.Button):
      # Require at least one filter (roster_mode counts if it's not None)
      if not any([
          self.cb, self.hydra, self.chimera, self.cvc, self.siege, self.playstyle,
          self.roster_mode is not None
      ]):
          await itx.response.send_message("Pick at least **one** filter, then try again. 🙂", ephemeral=True)
          return

      await itx.response.defer(thinking=True)
      try:
          rows = get_rows(False)
          matches = []
          for row in rows[1:]:
              try:
                  if is_header_row(row):
                      continue
                  if row_matches(row, self.cb, self.hydra, self.chimera, self.cvc, self.siege, self.playstyle):
                      spots_num = parse_spots_num(row[COL_E_SPOTS])
                      inact_num = parse_inactives_num(row[IDX_AF_INACTIVES] if len(row) > IDX_AF_INACTIVES else "")
                      if self.roster_mode == "open" and spots_num <= 0:
                          continue
                      if self.roster_mode == "full" and spots_num > 0:
                          continue
                      if self.roster_mode == "inactives" and inact_num <= 0:
                          continue
                      matches.append(row)
              except Exception:
                  continue

          if not matches:
              await itx.followup.send(
                  "No matching clans found. You might have set too many filter criteria — try again with fewer.",
                  ephemeral=False
              )
              return

          total_found = len(matches)
          cap = max(1, SEARCH_RESULTS_SOFT_CAP)
          cap_note = None
          if total_found > cap:
              matches = matches[:cap]
              cap_note = f"first {cap} of {total_found}"

          filters_text = format_filters_footer(
              self.cb, self.hydra, self.chimera, self.cvc, self.siege, self.playstyle, self.roster_mode
          )
          if cap_note:
              filters_text = f"{filters_text} • {cap_note}" if filters_text else cap_note

          if self.embed_variant == "search":
              view = MemberSearchPagedView(
                  author_id=itx.user.id,
                  rows=matches,
                  filters_text=filters_text,
                  guild=itx.guild,
                  timeout=900
              )
              ...
              sent = await itx.followup.send(embeds=embeds, files=files, view=view)
              view.message = sent
              self.results_message = sent
              return
          # recruiter variant omitted
      except Exception as e:
          try:
              await itx.followup.send(f"❌ Error: {type(e).__name__}: {e}", ephemeral=True)
          except Exception:
              pass
  ```

- **Helpers/utilities:** Filtering relies on `row_matches`, `parse_spots_num`, and canonicalized playstyle helpers.

  ```python
  # AUDIT/20251010_src/MM/bot_clanmatch_prefix.py:L296-L310
  def row_matches(row, cb, hydra, chimera, cvc, siege, playstyle) -> bool:
      if len(row) <= IDX_AB:
          return False
      if is_header_row(row):
          return False
      if not (row[COL_B_CLAN] or "").strip():
          return False
      return (
          cell_has_diff(row[COL_P_CB], cb) and
          cell_has_diff(row[COL_Q_HYDRA], hydra) and
          cell_has_diff(row[COL_R_CHIM], chimera) and
          cell_equals_10(row[COL_S_CVC], cvc) and
          cell_equals_10(row[COL_T_SIEGE], siege) and
          playstyle_ok(row[COL_U_STYLE], playstyle)
      )
  ```

- **Views & components:** `MemberSearchPagedView` manages pagination, embeds, attachment thumbnails, and mode toggles (lite, entry, profile) by deleting and re-sending result messages to maintain attachment integrity.

  ```python
  # AUDIT/20251010_src/MM/bot_clanmatch_prefix.py:L854-L1002 (excerpt)
  class MemberSearchPagedView(discord.ui.View):
      def __init__(self, *, author_id: int, rows, filters_text: str, guild: discord.Guild | None, timeout: float = 900):
          super().__init__(timeout=timeout)
          self.author_id = author_id
          self.rows = rows
          self.filters_text = filters_text
          self.guild = guild
          self.page = 0
          self.mode = "lite"  # 'lite' | 'entry' | 'profile'
          self.message: discord.Message | None = None
          self._sync_buttons()

      async def interaction_check(self, itx: discord.Interaction) -> bool:
          if itx.user and itx.user.id == self.author_id:
              return True
          ...  # sends ⚠️ Not your panel. Type **!clansearch** ...

      async def _build_page(self):
          ...
          for r in slice_:
              e = _build(r)
              tag = (r[COL_C_TAG] or "").strip()
              f, u = await build_tag_thumbnail(self.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
              if u and f:
                  e.set_thumbnail(url=u)
                  files.append(f)
              embeds.append(e)
          ...

      @discord.ui.button(emoji="📇", label="Short view", ... custom_id="ms_lite")
      async def ms_lite(self, itx: discord.Interaction, _btn: discord.ui.Button):
          self.mode = "lite"
          await self._edit(itx)
      # Additional buttons: Entry Criteria, Clan Profile, Prev/Next, Close
  ```

- **Cross-module links:** No other modules feed `!clansearch`; however, it shares helpers, caches, and the `ACTIVE_PANELS` registry with recruiter flows, so porting must preserve those shared behaviors.
- **Unused artifact:** `SearchResultFlipView` (defined at L1005-L1079) is currently unreferenced by the search flow, suggesting either legacy leftovers or a future single-result variant.

## 3) Data Sources & Config
- **Sheets/DB:** Reads from Google Sheets (`GSPREAD_CREDENTIALS`, `GOOGLE_SHEET_ID`, `WORKSHEET_NAME`, default `bot_info`). Columns are enumerated for row parsing; filters use columns P–U, entry criteria V–AB, with additional metadata through AF.
- **Caching:** `get_rows()` caches the entire worksheet for up to `SHEETS_CACHE_TTL_SEC` (default 8h). `clear_cache()` and scheduled refresh tasks (outside this section) invalidate it.
- **Environment:** Emoji proxy tuning, pagination size, role gates, and result caps all come from ENV. Emoji padding depends on `PUBLIC_BASE_URL`/`RENDER_EXTERNAL_URL`.

  ```python
  # AUDIT/20251010_src/MM/bot_clanmatch_prefix.py:L64-L166 (excerpt)
  CREDS_JSON = os.environ.get("GSPREAD_CREDENTIALS")
  SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
  WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "bot_info")
  ...
  SEARCH_RESULTS_SOFT_CAP = int(os.environ.get("SEARCH_RESULTS_SOFT_CAP", "25"))
  SHOW_TAG_IN_CLASSIC = os.environ.get("SHOW_TAG_IN_CLASSIC", "0") == "1"

  _gc = None
  _ws = None
  _cache_rows = None
  _cache_time = 0.0
  CACHE_TTL = int(os.environ.get("SHEETS_CACHE_TTL_SEC", "28800"))  # default 8h

  def get_rows(force: bool = False):
      if force or _cache_rows is None or (time.time() - _cache_time) > CACHE_TTL:
          ws = get_ws(False)
          _cache_rows = ws.get_all_values()
          _cache_time = time.time()
      return _cache_rows

  COL_A_RANK, COL_B_CLAN, COL_C_TAG, COL_D_LEVEL, COL_E_SPOTS = 0, 1, 2, 3, 4
  COL_F_PROGRESSION, COL_G_LEAD, COL_H_DEPUTIES = 5, 6, 7
  COL_I_CVC_TIER, COL_J_CVC_WINS, COL_K_SIEGE_TIER, COL_L_SIEGE_WINS = 8, 9, 10, 11
  COL_P_CB, COL_Q_HYDRA, COL_R_CHIM, COL_S_CVC, COL_T_SIEGE, COL_U_STYLE = 15, 16, 17, 18, 19, 20
  IDX_V, IDX_W, IDX_X, IDX_Y, IDX_Z, IDX_AA, IDX_AB = 21, 22, 23, 24, 25, 26, 27
  IDX_AC_RESERVED, IDX_AD_COMMENTS, IDX_AE_REQUIREMENTS = 28, 29, 30
  IDX_AF_INACTIVES = 31
  ```

- **Feature flags:** None specific to `!clansearch`; runtime toggles focus on emoji proxy strictness and panel behavior shared with recruiter tooling.

## 4) Observability & Reliability
- **Logging:** Module logger `log` exists but the search flow primarily uses `print` statements elsewhere. Errors inside the search handler are silently swallowed after notifying the user; there is no structured logging or correlation ID.
- **Metrics:** No counters or timers. Cache hits/misses are not instrumented.
- **Error handling:** User-visible failures include the validation errors noted above and a generic `❌ Error: {type(e).__name__}: {e}` follow-up if the search block raises. Background refresh tasks print to stdout when caches refresh or fail, but none tie specifically to member panels.
- **Reliability quirks:** `MemberSearchPagedView._edit` deletes and re-sends result messages on every mode toggle to keep attachments fresh, which can fail silently if deletion permissions are missing (fallback edits degrade gracefully). The command deletes the invoking message; if `ctx.reply` fails, no retry logic exists.

## 5) Performance Hotspots
- **Blocking calls:** `get_rows()` runs `ws.get_all_values()` synchronously on the event loop; this is the primary latency risk called directly from interaction handlers.
- **Attachment overhead:** Every page render re-fetches emoji binary data via `await emj.read()` and runs Pillow transformations (`build_tag_thumbnail`) serially, which scales with `PAGE_SIZE` and can stall interactions under load.
- **Pagination/batching:** Results are limited to 10 embeds per page (`PAGE_SIZE`) and further trimmed by the soft cap to keep output manageable. However, repeated searches spawn new result messages (the classic reuse path only applies to recruiter panels), so long sessions can accumulate embeds until Discord cleanup kicks in.
- **Cache usage:** Sheet cache is global and only refreshed on TTL expiry or external events; no partial refresh logic exists, so searches always iterate the entire dataset even for small filters.

## 6) Known TODOs / FIXMEs / Tech Debt
- **Async Sheets access:** The project backlog calls out replacing synchronous `get_rows()` usage in async handlers (critical for the search button) with thread offloading.

  ```markdown
  # AUDIT/20251010_src/MM/REVIEW/TODOS.md:L1-L11
  ## P0
  - **[F-01]** Replace direct `get_rows()` calls in async handlers with `asyncio.to_thread` helpers and add regression coverage for slow Sheets responses.
  ## P2
  - After F-01 lands, profile Sheets access to confirm no other hot-path synchronous calls remain.
  ```

- **Unused view:** `SearchResultFlipView` is currently unused; confirm intent before porting to avoid dead code or ensure wiring if members expect per-card flip buttons.
- **Result cleanup:** Member searches set `self.results_message` but never reuse it, so follow-up searches leave stale messages behind—worth addressing during porting.

## 7) Security & Privacy Notes
- **Data exposure:** Search results surface clan names, tags, entry requirements, and optional comments pulled straight from Sheets; ensure downstream bots respect the same visibility expectations.
- **Emoji proxy hardening:** The emoji padding helper only allows Discord CDN hosts and can be forced to proxy-only via `STRICT_EMOJI_PROXY`.
- **Permissions:** Lack of role gates means any guild member can enumerate sheet data; confirm this is acceptable for the destination bot or add gating/feature flags.
- **PII:** No direct member PII is exposed; data is clan-level. Ensure service account credentials remain protected when migrating.

## 8) Porting Risks (When Wiring Into New Bot)
- **Dependencies to replicate/shim:** Discord UI views, gspread service-account auth, Pillow image processing, and the emoji proxy endpoint (or an equivalent) must exist. The shared `ClanMatchView` class requires cross-feature utilities (`row_matches`, `build_tag_thumbnail`).
- **Stable contracts:** UI layout (dropdown placeholders, button labels), filtering semantics (case-insensitive style mapping, roster filter defaults), and `format_filters_footer` output must remain consistent for user muscle memory.
- **Behavioral invariants:**
  - Default roster filter is “Open Spots Only”; toggles cycle Open → Inactives → Full → Any.
  - Search button refuses blank criteria (unless roster reset to Any and no other filters).
  - Result footers always list active filters and add page/count info.
  - View-mode toggles should continue to rebuild the whole page to keep attachments valid.
- **Feature gating:** If the new bot introduces permission tiers, add a feature flag or role check to mirror current openness or to tighten it intentionally.
- **Operational assumptions:** Requires prefix command handling, access to message content intents, ability to delete user commands, permission to send embeds/files, and ideally threads not needed (member panels reply in-channel). Emoji assets must exist on the guild for thumbnail rendering.

## 9) Quick Inventory (Checklist)
- [x] Command entrypoints listed with file paths.
- [x] All external calls (Sheets/cache) enumerated.
- [x] ENV and flags enumerated with defaults/required.
- [x] All user-visible errors captured with message examples.
- [x] Logging & metrics callouts summarized.
- [x] Performance and reliability notes captured.
- [x] Porting risks and required shims listed.

## 10) Appendix — File Map
- `AUDIT/20251010_src/MM/bot_clanmatch_prefix.py` — Legacy prefix bot housing panels, search logic, embeds, and Sheets access.
- `AUDIT/20251010_src/MM/REVIEW/TODOS.md` — Backlog highlighting synchronous Sheets hot paths (relevant to the member search button).

Doc last updated: 2025-10-19 (v0.9.5)
