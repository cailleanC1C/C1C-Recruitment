# Cache Wiring Audit — 2025-11-07

## clans (shared/sheets/recruitment.py)
- **Sheet source:** `_sheet_id()` pulls `RECRUITMENT_SHEET_ID`, falling back to `GOOGLE_SHEET_ID` or `GSHEET_ID` if unset.
- **Config tab:** `_config_tab()` expects the `RECRUITMENT_CONFIG_TAB` worksheet (defaults to `Config`).
- **Data tab key:** `_clans_tab()` reads the `clans_tab` entry from the config sheet, defaulting to `bot_info` when missing.
- **Startup warm-up:** `cache_scheduler.preload_on_startup()` iterates `STARTUP_BUCKETS` and invokes `cache.refresh_now("clans", actor="startup")`.
- **Fallbacks / aliases:** Environment fallbacks for the sheet id and default tab name; config lookup scans alternate columns when `value` is blank.

```python
# shared/sheets/recruitment.py

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


def _config_tab() -> str:
    return os.getenv("RECRUITMENT_CONFIG_TAB", "Config")


def _load_config(force: bool = False) -> Dict[str, str]:
    global _CONFIG_CACHE, _CONFIG_CACHE_TS
    now = time.time()
    if not force and _CONFIG_CACHE and (now - _CONFIG_CACHE_TS) < _CONFIG_TTL:
        return _CONFIG_CACHE

    records = core.fetch_records(_sheet_id(), _config_tab())
    parsed: Dict[str, str] = {}
    for row in records:
        key_value: Optional[str] = None
        stored_value: Optional[str] = None
        for col, value in row.items():
            col_norm = (col or "").strip().lower()
            if col_norm == "key":
                key_value = str(value).strip().lower() if value is not None else ""
            elif col_norm in {"value", "val"}:
                stored_value = str(value).strip() if value is not None else ""
        if key_value:
            if stored_value:
                parsed[key_value] = stored_value
                continue
            for col, value in row.items():
                if (col or "").strip().lower() == "key":
                    continue
                if value is None:
                    continue
                candidate = str(value).strip()
                if candidate:
                    parsed[key_value] = candidate
                    break

    _CONFIG_CACHE = parsed
    _CONFIG_CACHE_TS = now
    return parsed


def _config_lookup(key: str, default: Optional[str] = None) -> Optional[str]:
    want = (key or "").strip().lower()
    if not want:
        return default
    config = _load_config()
    return config.get(want, default)


def _clans_tab() -> str:
    return _config_lookup("clans_tab", os.getenv("WORKSHEET_NAME", "bot_info")) or "bot_info"


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
    """Register recruitment cache buckets if they are not already present."""

    if cache.get_bucket("clans") is None:
        cache.register("clans", _TTL_CLANS_SEC, _load_clans_async)
    if cache.get_bucket("templates") is None:
        cache.register("templates", _TTL_TEMPLATES_SEC, _load_templates_async)
```

## templates (shared/sheets/recruitment.py)
- **Sheet source:** Shares `_sheet_id()` with the clans loader (same env fallbacks).
- **Config tab:** Same `_config_tab()` as clans; templates use that config sheet to resolve tab names.
- **Data tab key:** `_templates_tab()` reads the `welcome_templates_tab` key, defaulting to `WelcomeTemplates`.
- **Startup warm-up:** Included in `STARTUP_BUCKETS`, so `preload_on_startup()` refreshes templates at startup.
- **Fallbacks / aliases:** Defaults to `WelcomeTemplates` when the config row is absent.

```python
# shared/sheets/recruitment.py

def _templates_tab() -> str:
    return _config_lookup("welcome_templates_tab", "WelcomeTemplates") or "WelcomeTemplates"


async def _load_templates_async() -> List[Dict[str, Any]]:
    _ensure_service_account_credentials()
    sheet_id = _sheet_id()
    tab = _templates_tab()
    return await afetch_records(sheet_id, tab)


def register_cache_buckets() -> None:
    """Register recruitment cache buckets if they are not already present."""

    if cache.get_bucket("clans") is None:
        cache.register("clans", _TTL_CLANS_SEC, _load_clans_async)
    if cache.get_bucket("templates") is None:
        cache.register("templates", _TTL_TEMPLATES_SEC, _load_templates_async)
```

## clan_tags (shared/sheets/onboarding.py)
- **Sheet source:** `_sheet_id()` requires `ONBOARDING_SHEET_ID`, falling back to `GOOGLE_SHEET_ID` / `GSHEET_ID` if present.
- **Config tab:** `_config_tab()` expects `ONBOARDING_CONFIG_TAB` (default `Config`).
- **Data tab key:** `_clanlist_tab()` and `_resolve_onboarding_and_clanlist_tab()` read `CLANLIST_TAB` from config, defaulting to `ClanList` only in the lightweight helper; the resolver raises if the config key is empty.
- **Startup warm-up:** `clan_tags` is part of `STARTUP_BUCKETS`, so the preload loop refreshes it at startup.
- **Fallbacks / aliases:** Sheet id env fallbacks, default ClanList tab when config rows are missing.

```python
# shared/sheets/onboarding.py

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


def _config_tab() -> str:
    return os.getenv("ONBOARDING_CONFIG_TAB", "Config")


def _load_config(force: bool = False) -> Dict[str, str]:
    global _CONFIG_CACHE, _CONFIG_CACHE_TS
    now = time.time()
    if not force and _CONFIG_CACHE and (now - _CONFIG_CACHE_TS) < _CONFIG_TTL:
        return _CONFIG_CACHE

    records = core.fetch_records(_sheet_id(), _config_tab())
    parsed: Dict[str, str] = {}
    for row in records:
        key_value: Optional[str] = None
        stored_value: Optional[str] = None
        for col, value in row.items():
            col_norm = (col or "").strip().lower()
            if col_norm == "key":
                key_value = str(value).strip().lower() if value is not None else ""
            elif col_norm in {"value", "val"}:
                stored_value = str(value).strip() if value is not None else ""
        if key_value:
            if stored_value:
                parsed[key_value] = stored_value
                continue
            for col, value in row.items():
                if (col or "").strip().lower() == "key":
                    continue
                if value is None:
                    continue
                candidate = str(value).strip()
                if candidate:
                    parsed[key_value] = candidate
                    break

    _CONFIG_CACHE = parsed
    _CONFIG_CACHE_TS = now
    return parsed


def _config_lookup(key: str, default: Optional[str] = None) -> Optional[str]:
    want = (key or "").strip().lower()
    if not want:
        return default
    config = _load_config()
    return config.get(want, default)


def _clanlist_tab() -> str:
    return _config_lookup("clanlist_tab", "ClanList") or "ClanList"


def _resolve_onboarding_and_clanlist_tab() -> Tuple[str, str]:
    """Return the onboarding sheet id and configured clan list tab name."""

    sheet_id = _resolve_onboarding_sheet_id()
    cfg = _read_onboarding_config(sheet_id)
    tab = cfg.get("CLANLIST_TAB")
    if not tab:
        raise RuntimeError("Onboarding Config missing CLANLIST_TAB")
    return sheet_id, str(tab)


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
    """Register onboarding cache buckets if they are not already present."""

    if cache.get_bucket("clan_tags") is None:
        cache.register("clan_tags", _TTL_CLAN_TAGS_SEC, _load_clan_tags_async)
```

## onboarding_questions (shared/sheets/onboarding_questions.py)
- **Sheet source:** `_sheet_id()` trims `ONBOARDING_SHEET_ID` resolved via `get_onboarding_sheet_id()` and errors when empty.
- **Config tab:** `_question_tab()` → `resolve_onboarding_tab(cfg)` pulls `ONBOARDING_TAB` from the config mapping.
- **Data tab key:** `resolve_source()` returns `(sheet_id, tab)` for downstream loaders.
- **Startup warm-up:** `STARTUP_BUCKETS` includes `onboarding_questions`; the preload loop refreshes it alongside other caches, and `cache_service` registers the bucket via `register_onboarding_questions_bucket()`.
- **Fallbacks / aliases:** No alternate tab fallback; missing `ONBOARDING_TAB` raises `KeyError`.

```python
# shared/sheets/onboarding_questions.py

def _sheet_id() -> str:
    sheet_id = get_onboarding_sheet_id().strip()
    if not sheet_id:
        raise KeyError("missing config key: ONBOARDING_SHEET_ID")
    return sheet_id


def _question_tab() -> str:
    """Return the configured onboarding question tab name."""

    return resolve_onboarding_tab(cfg)


def resolve_source() -> tuple[str, str]:
    """Return the configured onboarding sheet identifier and tab name."""

    sheet_id = _sheet_id()
    tab = resolve_onboarding_tab(cfg)
    return sheet_id, tab


async def fetch_question_rows_async() -> Tuple[dict[str, str], ...]:
    """Fetch and normalise onboarding question rows from Sheets."""

    sheet_id = _sheet_id()
    tab = _question_tab()
    try:
        config_keys_count = len(cfg.keys())
    except Exception:
        config_keys_count = 0
    has_onboarding_tab = "ONBOARDING_TAB" in cfg
    log.info(
        "[refresh] bucket=onboarding_questions resolved_source",
        extra={
            "sheet_id": sheet_id,
            "config_tab": tab,
            "config_keys_count": config_keys_count,
            "has_ONBOARDING_TAB": "true" if has_onboarding_tab else "false",
        },
    )
    records = await afetch_records(sheet_id, tab)
    return _normalise_records(records)


def register_cache_buckets() -> None:
    """Register cache buckets used by onboarding questions."""

    from shared.sheets.cache_service import register_onboarding_questions_bucket

    register_onboarding_questions_bucket()
```

### Cache service registration (shared/sheets/cache_service.py)
```python
async def _load_onboarding_questions() -> Tuple[dict[str, str], ...]:
    """Load onboarding questions from Sheets via the async cache loader."""

    from shared.sheets.onboarding_questions import fetch_question_rows_async

    rows = await fetch_question_rows_async()
    return rows


def register_onboarding_questions_bucket() -> None:
    """Ensure the onboarding questions cache bucket is registered."""

    if cache.get_bucket("onboarding_questions") is not None:
        return
    cache.register(
        "onboarding_questions",
        _ONBOARDING_QUESTIONS_TTL_SEC,
        _load_onboarding_questions,
    )
```

### Scheduler hooks (shared/sheets/cache_scheduler.py)
```python
STARTUP_BUCKETS: tuple[str, ...] = (
    "clans",
    "clan_tags",
    "templates",
    "onboarding_questions",
)


@cron_task("refresh_onboarding_questions")
async def _cron_refresh_onboarding_questions(runtime: "rt.Runtime") -> None:
    await _run_refresh(runtime, _SPEC_BY_BUCKET["onboarding_questions"])


async def preload_on_startup() -> None:
    """Synchronously refresh core cache buckets during startup."""

    ensure_cache_registration()
    for name in STARTUP_BUCKETS:
        bucket = _safe_bucket(name)
        try:
            await cache.refresh_now(bucket, actor="startup")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            log.warning(
                LogTemplates.cache(
                    bucket=bucket,
                    ok=False,
                    duration_s=0.0,
                    retries=None,
                    reason=human_reason(exc),
                )
            )
```

## Observation
Currently reading sheet `ONBOARDING_SHEET_ID` (via `get_onboarding_sheet_id().strip()`) and tab `resolve_onboarding_tab(cfg)` (key `ONBOARDING_TAB`) for onboarding; this matches the expected ONBOARDING_SHEET_ID / config contract with `ONBOARDING_TAB`.

Doc last updated: 2025-11-07 (v0.9.7)
