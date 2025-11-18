# Audit — Current State of `!welcome` Command (Phase 6b)

## Executive summary
- `!welcome` only loads when the `recruitment_welcome` feature flag is enabled; the cog registers a single prefixed command guarded by staff RBAC helpers and tier metadata (`cogs/recruitment_welcome.py:L39-L83`).
- On invocation the command always pulls the `templates` cache bucket (WelcomeTemplates tab) and iterates rows looking for a `ClanTag` key that matches the provided clan argument (`shared/sheets/recruitment.py:L410-L445`).
- The clan tag argument is upper-cased and compared directly against `entry["ClanTag"]`; there is no normalization beyond stripping whitespace, so missing or differently named columns prevent any match (`cogs/recruitment_welcome.py:L56-L65`).
- The warning "⚠️ No template configured for clan tag `<tag>`." fires whenever no row matches the resolved tag, which is currently unavoidable because the live Sheet still exposes legacy columns such as `TAG`/`TITLE`/`BODY` instead of `ClanTag`/`Message` (legacy baseline at `AUDIT/legacy/.../welcome.py:L186-L209`).
- Because the template cache happily loads raw records, the command returns the warning even though data exists; there is no fallback to legacy field names nor any migration routine to translate templates (`shared/sheets/recruitment.py:L418-L445`).
- Secondary guardrails (cache TTL, refresh scheduler, docs) still assume the command works after a refresh, masking the schema mismatch as a "missing template" condition.
- No automated tests or mock fixtures exercise the welcome/template code path, so the regression went undetected (`rg "welcome" tests` → no matches).

## Repro steps
1. Ensure the `recruitment_welcome` toggle is enabled so the cog loads (`modules/common/runtime.py:L806-L834`).
2. Invoke the command from a staff-ranked account (passes `is_staff_member`/`is_admin_member` in `cogs/recruitment_welcome.py:L15-L30`).
3. Run `!welcome C1CE @Recruit` (any tag exhibiting the issue).
4. Bot responds in-channel with `⚠️ No template configured for clan tag `C1CE`.` — no additional log entry because the success logger sits after the failure return (`cogs/recruitment_welcome.py:L64-L80`).

## Code paths
- **Command entry point** — `cogs/recruitment_welcome.py:L39-L83`: registers `!welcome`, enforces staff tier, fetches cached templates, and handles errors.
- **Template fetcher** — `shared/sheets/recruitment.py:L410-L445`: pulls `WelcomeTemplates` via Sheets, caches rows for 7 days in the `templates` bucket, and exposes `get_cached_welcome_templates`.
- **Clan-tag resolver** — `cogs/recruitment_welcome.py:L56-L63`: upper-cases the provided clan argument and searches for a row whose `ClanTag` (upper-cased) matches exactly.
- **Error builder** — `cogs/recruitment_welcome.py:L64-L70`: emits the "No template configured" warning when no row matches, and the "missing 'Message' field" warning when a row lacks text.

## Data & config dependencies

### Environment
| Key | Purpose | Where Used |
| --- | --- | --- |
| `RECRUITMENT_SHEET_ID` / `GOOGLE_SHEET_ID` / `GSHEET_ID` | Identify the recruitment workbook backing both clan roster and templates. | `shared/sheets/recruitment.py:L242-L251` |
| `GSPREAD_CREDENTIALS` / `GOOGLE_SERVICE_ACCOUNT_JSON` | Provide the service-account JSON required before any Sheets fetch. | `shared/sheets/recruitment.py:L254-L261` |
| `RECRUITMENT_CONFIG_TAB` | Override the config worksheet that exposes tab aliases (including `welcome_templates_tab`). | `shared/sheets/recruitment.py:L264-L317` |
| `WORKSHEET_NAME` | Legacy fallback for the roster tab that feeds cache warmers (used when Config lacks `clans_tab`). | `shared/sheets/recruitment.py:L312-L314` |
| `SHEETS_CACHE_TTL_SEC` / `SHEETS_CONFIG_CACHE_TTL_SEC` | Control in-process TTL for clan/template caches and config lookups. | `shared/sheets/recruitment.py:L11-L20` |

### Sheets & columns
| Sheet / Tab | Column Name | Purpose | Where Used |
| --- | --- | --- | --- |
| Recruitment sheet (`Config`) | `welcome_templates_tab` | Names the worksheet holding welcome templates; defaults to `WelcomeTemplates`. | `shared/sheets/recruitment.py:L264-L317` |
| Recruitment sheet (`WelcomeTemplates`) | `ClanTag` | Expected primary key for template lookup; current code rejects rows without it. | `cogs/recruitment_welcome.py:L56-L65` |
| Recruitment sheet (`WelcomeTemplates`) | `Message` | Expected text body appended to command output. | `cogs/recruitment_welcome.py:L68-L74` |
| Recruitment sheet (`FeatureToggles`) | `feature_name` / `enabled` (entry `recruitment_welcome`) | Enables loading of the welcome cog during runtime bootstrap. | `modules/common/runtime.py:L806-L823`; `modules/common/feature_flags.py:L128-L200` |

## Decision chart
| Step | Condition / Action | Success Path | Failure Path |
| --- | --- | --- | --- |
| 1 | Runtime bootstrap checks `recruitment_welcome` toggle before loading the cog. | Cog registers `!welcome`. | Command absent; users see "Unknown command". |
| 2 | `!welcome <tag> <@user>` invoked by actor. | Continue if `is_staff_member`/`is_admin_member` true. | `staff_only` replies "Staff only." and raises (`cogs/recruitment_welcome.py:L15-L30`). |
| 3 | Fetch `templates = get_cached_welcome_templates()`. | Cached rows (possibly stale) returned. | If cache empty → reply `⚠️ No welcome templates found...` (`cogs/recruitment_welcome.py:L51-L54`). |
| 4 | Normalize input tag to uppercase (`tag = clan.strip().upper()`). | Iterate rows comparing to `entry["ClanTag"]`. | Blank tag → falls through to failure message. |
| 5 | Locate matching row. | Found row → proceed to step 6. | Not found → warning `⚠️ No template configured for clan tag `<tag>`.` |
| 6 | Pull `Message` text and append optional note. | Sends welcome text, logs `[welcome] actor=...`. | Missing `Message` → warning `⚠️ Template for `<tag>` is missing a 'Message' field.` |

## Why C1CE/C1CM fail right now
- The command only recognizes rows containing a `ClanTag` field, but the legacy sheet schema still exposes `TAG` alongside `TITLE`, `BODY`, and `FOOTER` (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L186-L209`).
- `core.fetch_records` preserves the exact header case from Sheets; there is no transformation that would populate a synthetic `ClanTag`, so every row returns `entry.get("ClanTag") == ""` and the search loop never matches (`shared/sheets/recruitment.py:L418-L445`).
- Because no match is found, the command exits at the "No template configured" branch before it ever evaluates message content, even though valid text exists under the old `TITLE`/`BODY` columns.
- Tags like `C1CE`/`C1CM` therefore fail regardless of note or mention: the bot is looking for a new schema key that has not been provisioned in production data.

## Legacy `!welcome` workflow & parity requirements
- **Template ingestion and default fallbacks.** Legacy Matchmaker cached rows keyed by `TAG`, merged each clan with the `C1C` default row to backfill missing TITLE/BODY/FOOTER text, and tracked additional routing fields such as `TARGET_CHANNEL_ID`, `PING_USER`, and crest URLs (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L203-L257`). Any reimplementation must keep the per-tag cache, the `C1C` fallback merge, and non-text metadata so that incomplete clan rows still post with the shared copy and channel targeting intact.
- **Rich text expansion.** The legacy command replaced tokens like `{MENTION}`, `{USERNAME}`, `{CLAN}`, `{NOW}`, `{INVITER}`, `{CLANLEAD}`, `{DEPUTIES}`, and custom emoji macros (`{EMOJI:name}` or ID) before stripping empty role sections to avoid awkward blanks in embeds (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L32-L159` and `L258-L347`). The new bot needs to port these substitutions and cleanup rules so welcome copy renders with mentions, timestamps, and optional role lists exactly as authored.
- **Permission model and operational toggles.** Matchmaker enforced role-based access, supported runtime enable/disable overrides, exposed `!welcome-refresh`/`!welcome-on`/`!welcome-off`/`!welcome-status`, and logged every action to a dedicated channel (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L183-L443`). The migration plan should preserve staff-only gating, cooldowns, logging, manual template reloads, and the ability to suspend the module without redeploying.
- **Delivery flow and multichannel output.** The legacy command posted an embed to the clan’s configured channel, optionally pinged the recruit, pushed a generalized notice to the community channel, attached crest thumbnails, and deleted the invoking message for hygiene (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L333-L405`). Replicating this flow in the new environment avoids regressions in announcement styling, follow-up pings, and audit logs.
- **Error handling and operator feedback.** When configuration gaps occurred (missing row, bad channel ID, empty body), the old cog replied with actionable guidance and still wrote structured log entries for traceability (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L329-L405`). The simplified new handler only emits a generic missing-template warning (`cogs/recruitment_welcome.py:L56-L80`); future work must restore granular replies so staff can triage sheet issues quickly.

### Bridging legacy behavior into the new bot
- **Schema translation layer.** Until the Sheets tab is migrated, introduce a loader that maps legacy columns (`TAG`, `TITLE`, `BODY`, `FOOTER`, `PING_USER`, etc.) into the modern structure, while still accepting the future `ClanTag`/`Message` keys for forward compatibility (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L221-L238`; `cogs/recruitment_welcome.py:L51-L75`).
- **Embed composer.** Replace the current plain-text `ctx.send` with an embed builder that mirrors the legacy formatting, supports crest thumbnails, footer emoji icons, optional notes, and combined TITLE/BODY/FOOTER sections before dispatching to the clan channel (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L339-L390`).
- **General notice + cleanup tasks.** Reintroduce the post-send general announcement and command cleanup coroutine so operations keep the server-wide signal and tidy channels, wiring both through the runtime logging utilities already present in the modern repo (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L282-L405`; `modules/common/runtime.py:L806-L834`).
- **Administrative surface area.** Port the refresh/on/off/status commands (or slash equivalents) to ensure staff can warm caches and flip the feature without code pushes, while aligning checks with the modern `tier("staff")` decorators (`AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py:L407-L443`; `cogs/recruitment_welcome.py:L39-L83`).

## Parity & docs check
- **Command matrix** still advertises a working `!welcome [clan] @mention` with no schema caveats, matching the old behavior but not the current code requirement for `ClanTag`/`Message` columns (`docs/ops/CommandMatrix.md:L30-L47`).
- **Troubleshooting.md** suggests running `!rec refresh templates` when a template is missing, implying cache staleness rather than schema mismatch (`docs/Troubleshooting.md:L13-L21`).
- The root README promises "!welcome — staff command that posts the standard welcome note" which is false given the present failure mode (`README.md:L4-L16`).
- No doc mentions a migration to a single `Message` column or the new `ClanTag` header, so operators have no guidance to reconcile the sheets with the updated code.

## Test coverage
- No automated tests reference `welcome` or `templates`; repository search confirms zero matches under `tests/` (`rg "welcome" tests -n`). The entire flow relies on manual verification.

## Next steps (no code yet)
- **Sheet migration:** Add `ClanTag` and `Message` columns (or rename existing ones) in `WelcomeTemplates`, backfill values for every clan, and drop legacy columns after validation. Pros: zero code change, aligns with new schema expectations. Cons: manual sheet edits, coordination risk, potential breakage for downstream tooling expecting `TITLE`/`BODY`.
- **Compatibility shim in code:** Map legacy `TAG` → `ClanTag` and concatenate `TITLE`/`BODY`/`FOOTER` into `Message` during template load. Pros: restores functionality without sheet churn, supports gradual migration. Cons: requires code update + tests, adds maintenance debt if both schemas must coexist.
- **Config-driven mapping:** Introduce a Config/feature flag entry indicating which schema is live, then branch template parsing accordingly. Pros: explicit migration toggle, safe staged rollout. Cons: increases configuration complexity and still demands code work + documentation updates.
- **Operational fallback:** Until a fix ships, document the failure and direct staff to manually paste welcome copy; optionally disable the `recruitment_welcome` feature to avoid misleading command exposure. Pros: quick mitigation. Cons: no automation, risks inconsistent messaging.

## Appendix

### ripgrep excerpts
```text
$ rg "No template configured" -n
cogs/recruitment_welcome.py
65:            await ctx.send(f"⚠️ No template configured for clan tag `{tag}`.")
```

```text
$ rg "@commands.command(name=\"welcome\"" -n
cogs/recruitment_welcome.py
40:    @commands.command(name="welcome", usage="[clan] @mention")
AUDIT/legacy/clanmatch-welcomecrew/2025-10-10_code-export/MM/welcome.py
303:    @commands.command(name="welcome")
```

```text
$ rg "welcome" tests -n
(root)  # no matches
```

### Call graph snapshot
- `discord.ext.commands.Command` → `WelcomeBridge.welcome()` (`cogs/recruitment_welcome.py:L39-L83`).
  - Calls `shared.sheets.async_facade.get_cached_welcome_templates()` → thread off to `shared/sheets/recruitment.get_cached_welcome_templates()` (`shared/sheets/async_facade.py:L54-L101`; `shared/sheets/recruitment.py:L410-L445`).
  - Iterates templates; on success sends composed message then logs via `modules.common.runtime.send_log_message` (`cogs/recruitment_welcome.py:L68-L80`).
  - On failure (no row or missing message) returns early with the relevant warning (`cogs/recruitment_welcome.py:L64-L70`).
