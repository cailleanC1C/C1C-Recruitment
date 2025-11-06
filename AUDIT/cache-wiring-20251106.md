# Cache wiring audit — 2025-11-06

This document captures the current wiring for the four sheet-backed caches as of today; it is descriptive only and does not propose code changes.

## clans

### Sheet resolution
`clans` resolves the recruitment workbook via `RECRUITMENT_SHEET_ID` (falling back to legacy aliases) and reads the tab configured under the `clans_tab` key, defaulting to `bot_info` when configuration is absent.

```python title="shared/sheets/recruitment.py#L242-L317"
# excerpt
def _sheet_id() -> str:
    sheet_id = (
        os.getenv("RECRUITMENT_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    ).strip()
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID not set")
    return sheet_id


def _config_lookup(key: str, default: Optional[str] = None) -> Optional[str]:
    want = (key or "").strip().lower()
    if not want:
        return default
    config = _load_config()
    return config.get(want, default)


def _clans_tab() -> str:
    return _config_lookup("clans_tab", os.getenv("WORKSHEET_NAME", "bot_info")) or "bot_info"
```

### Cache registration
`register_cache_buckets()` installs the `clans` bucket with a three-hour TTL and points it at the async loader that fetches and sanitizes the configured tab.

```python title="shared/sheets/recruitment.py#L454-L486"
# excerpt
async def _load_clans_async() -> List[List[str]]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _clans_tab()
    rows = await afetch_values(sheet_id, tab)
    now = time.time()
    sanitized = _process_clan_sheet(rows, now, tab)
    global _CLAN_ROWS, _CLAN_ROWS_TS, _CLAN_TAG_INDEX, _CLAN_TAG_INDEX_TS
    _CLAN_ROWS = sanitized
    _CLAN_ROWS_TS = now
    _CLAN_TAG_INDEX = _build_tag_index(sanitized)
    _CLAN_TAG_INDEX_TS = now
    return sanitized


def register_cache_buckets() -> None:
    if cache.get_bucket("clans") is None:
        cache.register("clans", _TTL_CLANS_SEC, _load_clans_async)
```

### Startup warm-up
The shared cache preloader iterates every registered bucket (including `clans`) 15 seconds after launch and forces a refresh via cache telemetry.

```python title="modules/common/runtime.py#L158-L220"
# excerpt
async def _startup_preload(bot: commands.Bot | None = None) -> None:
    await asyncio.sleep(15)
    runtime = get_active_runtime()
    if bot is None and runtime is not None:
        bot = runtime.bot
    if bot is None:
        log.warning("Cache preloader aborted: bot unavailable")
        return
    from shared.cache import telemetry as cache_telemetry
    bucket_names = cache_telemetry.list_buckets()
    if not bucket_names:
        log.info("Cache preloader skipped: no cache buckets registered")
        return
    for name in bucket_names:
        try:
            result = await cache_telemetry.refresh_now(
                name=name,
                actor="startup",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("startup preload refresh failed", extra={"bucket": name})
            await send_log_message(f"❌ Startup refresh failed for {name}: {exc}")
            continue
        snapshot = result.snapshot
        duration_ms = result.duration_ms or 0
        total_ms += duration_ms
        raw_result = snapshot.last_result or ("ok" if result.ok else "fail")
```

### Scheduler
Runtime startup registers the `clans` bucket for a 3 h cadence and wires the cron handler that calls back into the cache scheduler.

```python title="modules/common/runtime.py#L839-L855"
# excerpt
ensure_cache_registration()
cache_specs = (
    ("clans", timedelta(hours=3), "3h"),
    ("templates", timedelta(days=7), "7d"),
    ("clan_tags", timedelta(days=7), "7d"),
    ("onboarding_questions", timedelta(days=7), "7d"),
)
for bucket, interval, cadence in cache_specs:
    spec, job = register_refresh_job(
        self,
        bucket=bucket,
        interval=interval,
        cadence_label=cadence,
    )
```

```python title="shared/sheets/cache_scheduler.py#L127-L151"
# excerpt
@cron_task("refresh_clans")
async def _cron_refresh_clans(runtime: "rt.Runtime") -> None:
    await _run_refresh(runtime, _SPEC_BY_BUCKET["clans"])
```

### Consumers (current)
- `modules/recruitment/search.fetch_roster_records` loads cached roster rows (or forces a refresh when `force=True`) and normalizes them for downstream filters.

```python title="modules/recruitment/search.py#L35-L41"
# excerpt
async def fetch_roster_records(*, force: bool = False) -> list[RecruitmentClanRecord]:
    records: Iterable[RecruitmentClanRecord] = await sheets.fetch_clan_records(
        force=force
    )
    return normalize_records(list(records))
```

- `modules/recruitment/views/member_panel.MemberPanel._load_rows` pulls clan rows through the async facade to populate member search panels.

```python title="modules/recruitment/views/member_panel.py#L458-L464"
# excerpt
async def _load_rows(self) -> list[RecruitmentClanRecord]:
    try:
        records = await fetch_clans_async(force=False)
    except Exception:
        log.exception("failed to fetch member clan rows")
        return []
    return roster_search.normalize_records(list(records))
```

- `cogs/recruitment_clan_profile.ClanProfileCog.clan` resolves individual clan records via the cache-backed tag lookup before rendering the profile embed.

```python title="cogs/recruitment_clan_profile.py#L74-L82"
# excerpt
row = await sheets.get_clan_by_tag(normalized)
if row is None:
    await ctx.reply(embed=_error_embed(normalized), mention_author=False)
    return
```

## templates

### Sheet resolution
`templates` shares the recruitment workbook resolver and reads the tab configured under `welcome_templates_tab`, defaulting to `WelcomeTemplates` when the config row is empty.

```python title="shared/sheets/recruitment.py#L242-L317"
# excerpt
def _sheet_id() -> str:
    sheet_id = (
        os.getenv("RECRUITMENT_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    ).strip()
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID not set")
    return sheet_id


def _templates_tab() -> str:
    return _config_lookup("welcome_templates_tab", "WelcomeTemplates") or "WelcomeTemplates"
```

### Cache registration
The recruitment cache registrar installs the `templates` bucket alongside `clans`, pointing at the async loader that fetches `WelcomeTemplates` records.

```python title="shared/sheets/recruitment.py#L471-L486"
# excerpt
async def _load_templates_async() -> List[Dict[str, Any]]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _templates_tab()
    return await afetch_records(sheet_id, tab)


def register_cache_buckets() -> None:
    if cache.get_bucket("templates") is None:
        cache.register("templates", _TTL_TEMPLATES_SEC, _load_templates_async)
```

### Startup warm-up
The same startup preloader issues a `cache_telemetry.refresh_now("templates")` call in its bucket loop, loading the welcome template rows into memory before commands execute.

```python title="modules/common/runtime.py#L172-L205"
# excerpt
bucket_names = cache_telemetry.list_buckets()
if not bucket_names:
    log.info("Cache preloader skipped: no cache buckets registered")
    return
for name in bucket_names:
    try:
        result = await cache_telemetry.refresh_now(
            name=name,
            actor="startup",
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("startup preload refresh failed", extra={"bucket": name})
        await send_log_message(f"❌ Startup refresh failed for {name}: {exc}")
        continue
    snapshot = result.snapshot
    duration_ms = result.duration_ms or 0
```

### Scheduler
The runtime registers a weekly cron for templates; the cache scheduler binds the `refresh_templates` cron task to `_run_refresh`.

```python title="modules/common/runtime.py#L839-L855"
# excerpt
cache_specs = (
    ("clans", timedelta(hours=3), "3h"),
    ("templates", timedelta(days=7), "7d"),
    ("clan_tags", timedelta(days=7), "7d"),
    ("onboarding_questions", timedelta(days=7), "7d"),
)
for bucket, interval, cadence in cache_specs:
    spec, job = register_refresh_job(
        self,
        bucket=bucket,
        interval=interval,
        cadence_label=cadence,
    )
```

```python title="shared/sheets/cache_scheduler.py#L132-L134"
# excerpt
@cron_task("refresh_templates")
async def _cron_refresh_templates(runtime: "rt.Runtime") -> None:
    await _run_refresh(runtime, _SPEC_BY_BUCKET["templates"])
```

### Consumers (current)
- `modules/recruitment/welcome._load_templates` retrieves cached WelcomeTemplates rows (falling back to a live fetch if the bucket is empty) and builds normalized template objects.

```python title="modules/recruitment/welcome.py#L200-L225"
# excerpt
async def _load_templates() -> tuple[dict[str, WelcomeTemplate], Optional[WelcomeTemplate]]:
    rows = sheets.get_cached_welcome_templates()
    templates: dict[str, WelcomeTemplate] = {}
    default_row: WelcomeTemplate | None = None
    for row in rows or []:
        template = _build_template(row)
        if template is None:
            continue
        key = template.tag
        if key in {"C1C", "DEFAULT"}:
            if key == "C1C":
                default_row = template
            else:
                alt_default = template
            continue
        templates[key] = template
    default_row = default_row or alt_default
    merged: dict[str, WelcomeTemplate] = {}
    for key, template in templates.items():
        merged[key] = template.merged_with(default_row)
    return merged, default_row
```

- `modules/recruitment/welcome.WelcomeCommandService.post_welcome` loads the cache via `_load_templates()` before composing the outbound welcome message for a clan.

```python title="modules/recruitment/welcome.py#L391-L418"
# excerpt
try:
    templates, default_row = await _load_templates()
except Exception as exc:
    await _log("error", actor=getattr(ctx.author, "id", None), tag=tag, error=repr(exc))
    await ctx.reply("⚠️ Failed to load welcome templates. Try again after the next refresh.")
    return

template = templates.get(tag)
if template is None:
    await _log("error", actor=getattr(ctx.author, "id", None), tag=tag, cause="missing_row")
    await ctx.reply(f"I can't find a configured welcome for **{tag}**. Add it in the sheet.")
    return
```

- `modules/recruitment/welcome.WelcomeCommandService.refresh_templates` exposes the admin command that refreshes the `templates` bucket via telemetry and surfaces the result to Discord.

```python title="modules/recruitment/welcome.py#L581-L604"
# excerpt
async def refresh_templates(self, ctx: commands.Context) -> None:
    actor = getattr(ctx.author, "mention", None) or getattr(ctx.author, "id", None)
    result = await cache_telemetry.refresh_now("templates", actor=str(actor))
    bucket_results = refresh_bucket_results([result])
    deduper = refresh_deduper()
    bucket_name = getattr(result, "name", "templates") or "templates"
    key = refresh_dedupe_key("templates", None, [bucket_name])
    if deduper.should_emit(key):
        await rt.send_log_message(
            format_refresh_message(
                "templates",
                bucket_results,
                total_s=(result.duration_ms or 0) / 1000.0 if result.duration_ms is not None else None,
            )
        )
    if result.ok:
        await ctx.reply("Welcome templates reloaded. ✅")
    else:
        error = result.error or "unknown error"
        await ctx.reply(f"Reload failed: `{error}`")
```

## clan_tags

### Sheet resolution
`clan_tags` resolves the onboarding workbook (`ONBOARDING_SHEET_ID` or its aliases) and reads the tab configured as `clanlist_tab`, defaulting to `ClanList` when the config row is absent.

```python title="shared/sheets/onboarding.py#L24-L177"
# excerpt
def _sheet_id() -> str:
    sheet_id = (
        os.getenv("ONBOARDING_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("GSHEET_ID")
        or ""
    )
    sheet_id = sheet_id.strip()
    if not sheet_id:
        raise RuntimeError("ONBOARDING_SHEET_ID not set")
    return sheet_id


def _clanlist_tab() -> str:
    return _config_lookup("clanlist_tab", "ClanList") or "ClanList"


def _resolve_onboarding_and_clanlist_tab() -> Tuple[str, str]:
    sheet_id = _resolve_onboarding_sheet_id()
    cfg = _read_onboarding_config(sheet_id)
    tab = cfg.get("CLANLIST_TAB")
    if not tab:
        raise RuntimeError("Onboarding Config missing CLANLIST_TAB")
    return sheet_id, str(tab)
```

### Cache registration
The onboarding registrar installs the `clan_tags` bucket with a seven-day TTL, using the async loader that pulls the configured ClanList tab.

```python title="shared/sheets/onboarding.py#L390-L439"
# excerpt
def load_clan_tags(force: bool = False) -> List[str]:
    values = core.fetch_values(_sheet_id(), _clanlist_tab())
    tags: List[str] = []
    for row in values[1:]:
        if not row:
            continue
        tag = (row[0] if len(row) > 0 else "").strip().upper()
        if tag:
            tags.append(tag)
    _CLAN_TAGS = tags
    _CLAN_TAG_TS = now
    return tags


async def _load_clan_tags_async() -> List[str]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _clanlist_tab()
    values = await afetch_values(sheet_id, tab)
    tags: List[str] = []
    for row in values[1:]:
        if not row:
            continue
        tag = (row[0] if len(row) > 0 else "").strip().upper()
        if tag:
            tags.append(tag)
    return tags


def register_cache_buckets() -> None:
    if cache.get_bucket("clan_tags") is None:
        cache.register("clan_tags", _TTL_CLAN_TAGS_SEC, _load_clan_tags_async)
```

### Startup warm-up
Startup preload invokes `cache_telemetry.refresh_now("clan_tags")` through the generic loop shown earlier, so clan tags are loaded alongside the other buckets after the initial 15 s delay.

```python title="modules/common/runtime.py#L172-L205"
# excerpt
for name in bucket_names:
    try:
        result = await cache_telemetry.refresh_now(
            name=name,
            actor="startup",
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("startup preload refresh failed", extra={"bucket": name})
        await send_log_message(f"❌ Startup refresh failed for {name}: {exc}")
        continue
    snapshot = result.snapshot
    duration_ms = result.duration_ms or 0
    total_ms += duration_ms
```

### Scheduler
`clan_tags` is registered for a weekly refresh cadence, and the scheduler decorates a dedicated cron handler that runs `_run_refresh` for that bucket.

```python title="modules/common/runtime.py#L839-L855"
# excerpt
cache_specs = (
    ("clans", timedelta(hours=3), "3h"),
    ("templates", timedelta(days=7), "7d"),
    ("clan_tags", timedelta(days=7), "7d"),
    ("onboarding_questions", timedelta(days=7), "7d"),
)
for bucket, interval, cadence in cache_specs:
    spec, job = register_refresh_job(
        self,
        bucket=bucket,
        interval=interval,
        cadence_label=cadence,
    )
```

```python title="shared/sheets/cache_scheduler.py#L137-L139"
# excerpt
@cron_task("refresh_clan_tags")
async def _cron_refresh_clan_tags(runtime: "rt.Runtime") -> None:
    await _run_refresh(runtime, _SPEC_BY_BUCKET["clan_tags"])
```

### Consumers (current)
- Startup preload invokes `cache_telemetry.refresh_now("clan_tags")`, ensuring the clan tag list is hydrated before features attempt to use it.

```python title="modules/common/runtime.py#L182-L199"
# excerpt
for name in bucket_names:
    try:
        result = await cache_telemetry.refresh_now(
            name=name,
            actor="startup",
        )
    except asyncio.CancelledError:
        raise
```

- `shared/sheets.onboarding.load_clan_tags` remains the synchronous accessor; it still performs a direct `fetch_values` call against the ClanList tab when the in-module TTL expires, bypassing the async cache.

```python title="shared/sheets/onboarding.py#L390-L408"
# excerpt
def load_clan_tags(force: bool = False) -> List[str]:
    values = core.fetch_values(_sheet_id(), _clanlist_tab())
    tags: List[str] = []
    for row in values[1:]:
        if not row:
            continue
        tag = (row[0] if len(row) > 0 else "").strip().upper()
        if tag:
            tags.append(tag)
    _CLAN_TAGS = tags
    _CLAN_TAG_TS = now
    return tags
```

## onboarding_questions

### Sheet resolution
`onboarding_questions` derives its worksheet from the onboarding workbook resolver and uses the `ONBOARDING_TAB` config entry (resolved via `resolve_onboarding_tab(cfg)`) to select the appropriate question tab.

```python title="shared/sheets/onboarding_questions.py#L11-L62"
# excerpt
from shared.config import cfg, resolve_onboarding_tab
from shared.sheets import onboarding as onboarding_sheets


def _question_tab() -> str:
    return resolve_onboarding_tab(cfg)


def _sheet_id() -> str:
    return onboarding_sheets._sheet_id()  # type: ignore[attr-defined]
```

### Cache registration
`register_cache_buckets()` calls back into the shared cache service to ensure the `onboarding_questions` bucket exists with a seven-day TTL and the async loader that fetches and normalizes question rows.

```python title="shared/sheets/onboarding_questions.py#L79-L108"
# excerpt
async def fetch_question_rows_async() -> Tuple[dict[str, str], ...]:
    sheet_id = _sheet_id()
    records = await afetch_records(sheet_id, _question_tab())
    return _normalise_records(records)


def _cached_rows() -> Tuple[dict[str, str], ...]:
    from shared.sheets.cache_service import cache
    bucket = cache.get_bucket("onboarding_questions")
    if bucket is None:
        _cached_rows_snapshot = None
        _cached_questions_by_flow.clear()
        raise RuntimeError("onboarding_questions cache bucket is not registered")
    value = bucket.value
    if value is None:
        _cached_rows_snapshot = None
        _cached_questions_by_flow.clear()
        raise RuntimeError("onboarding_questions cache is empty (should be preloaded)")
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, Iterable):
        return tuple(dict(row) for row in value)
    raise TypeError("unexpected onboarding_questions cache payload")
```

```python title="shared/sheets/onboarding_questions.py#L271-L276"
# excerpt
def register_cache_buckets() -> None:
    from shared.sheets.cache_service import register_onboarding_questions_bucket
    register_onboarding_questions_bucket()
```

```python title="shared/sheets/cache_service.py#L250-L258"
# excerpt
def register_onboarding_questions_bucket() -> None:
    if cache.get_bucket("onboarding_questions") is not None:
        return
    cache.register(
        "onboarding_questions",
        _ONBOARDING_QUESTIONS_TTL_SEC,
        _load_onboarding_questions,
    )
```

### Startup warm-up
The generic preload loop refreshes the `onboarding_questions` bucket alongside the others, surfacing startup failures if the sheet is misconfigured.

```python title="modules/common/runtime.py#L172-L205"
# excerpt
for name in bucket_names:
    try:
        result = await cache_telemetry.refresh_now(
            name=name,
            actor="startup",
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("startup preload refresh failed", extra={"bucket": name})
        await send_log_message(f"❌ Startup refresh failed for {name}: {exc}")
        continue
    snapshot = result.snapshot
    duration_ms = result.duration_ms or 0
```

### Scheduler
`onboarding_questions` is scheduled for a weekly refresh; the cron decorator binds the bucket to `_run_refresh` with the same cadence as the other 7 d jobs.

```python title="modules/common/runtime.py#L839-L855"
# excerpt
cache_specs = (
    ("clans", timedelta(hours=3), "3h"),
    ("templates", timedelta(days=7), "7d"),
    ("clan_tags", timedelta(days=7), "7d"),
    ("onboarding_questions", timedelta(days=7), "7d"),
)
for bucket, interval, cadence in cache_specs:
    spec, job = register_refresh_job(
        self,
        bucket=bucket,
        interval=interval,
        cadence_label=cadence,
    )
```

```python title="shared/sheets/cache_scheduler.py#L142-L144"
# excerpt
@cron_task("refresh_onboarding_questions")
async def _cron_refresh_onboarding_questions(runtime: "rt.Runtime") -> None:
    await _run_refresh(runtime, _SPEC_BY_BUCKET["onboarding_questions"])
```

### Consumers (current)
- `modules/onboarding/ui/summary_embed.render_questions_summary` renders per-thread summaries by pulling cached questions and comparing hashes for drift detection.

```python title="modules/onboarding/ui/summary_embed.py#L53-L64"
# excerpt
questions = onboarding_questions.get_questions(flow)
expected_hash = onboarding_questions.schema_hash(flow)
if schema_hash and schema_hash != expected_hash:
    log.warning(
        "onboarding.summary.schema_mismatch %s",
        {"flow": flow, "expected": expected_hash, "received": schema_hash},
    )
for question in questions:
    if _is_hidden(question.qid, visibility):
        continue
```

- `modules/onboarding/welcome_flow.open_questions` reads the cached schema (and hash) before launching the in-thread questionnaire, logging and aborting if the loader fails.

```python title="modules/onboarding/welcome_flow.py#L153-L173"
# excerpt
try:
    questions = onboarding_questions.get_questions(flow)
    schema_version = onboarding_questions.schema_hash(flow)
except Exception as exc:
    await logs.send_welcome_exception(
        "error",
        exc,
        **_context({"result": "schema_load_failed", **context_defaults}),
    )
    return

await logs.send_welcome_log(
    "info",
    **_context(
        {
            "result": "started",
            "schema": schema_version,
            "questions": len(questions),
            **context_defaults,
        }
    ),
)
```

- `modules/onboarding/controllers/welcome_controller.WelcomeController._rehydrate_questions` reloads the cache on-demand when restoring a ticket session, storing the question set per thread.

```python title="modules/onboarding/controllers/welcome_controller.py#L1650-L1663"
# excerpt
try:
    from shared.sheets import onboarding_questions
except Exception:
    return False

try:
    refreshed = onboarding_questions.get_questions(self.flow)
except Exception:
    log.warning(
        "failed to rehydrate welcome questions", exc_info=True
    )
    raise

self._questions[thread_id] = list(refreshed)
```

## Notes / gaps
- `shared.sheets.onboarding.load_clan_tags` still issues synchronous `fetch_values` calls when its internal TTL expires; no production feature currently reads the `clan_tags` cache directly beyond the startup warm-up.
- All four buckets rely on the shared preloader; if registration fails before `_startup_preload` runs, the warm-up loop silently skips that bucket until the next manual refresh or scheduler interval.

Doc last updated: 2025-11-06 (v0.9.7)
