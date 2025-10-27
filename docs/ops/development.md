# CoreOps Development Notes

## Telemetry helpers only
- Import telemetry data via `c1c_coreops.cache_public` helpers (`list_buckets`,
  `get_snapshot`, `refresh_now`).
- Never import or reference private cache attributes (anything prefixed with `_`). Guard
  checks in CI will fail the build if private modules leak into the cog.

## Preloader contract
- Startup automatically executes `refresh_now(name, actor="startup")` for every registered
  bucket.
- Buckets must tolerate multiple sequential refreshes; ensure idempotent warmers when
  adding new data sources.

## Runtime caveats
- Render free tier does not persist the cache between restarts. Treat every reboot as a
  cold start and rely on the preloader warm-up.
- Local development mirrors this behavior: the `.cache/` folder is not used, and no JSON
  snapshots persist across runs.

## Sheets access
- Async code must go through `shared.sheets.async_facade`; the synchronous helpers now
  exist solely for cache warmers and CLI scripts.
- Legacy retry wrappers (`_legacy_fetch`, `retry_safe_read`) were removed in the audit
  cleanup; any remaining imports should be replaced with the async facade.

## Testing commands
- `!rec refresh all` — verify cache warmers and actor logging.
- `!rec digest` — confirm public telemetry includes age/next/retries and fallback text.
- `!checksheet --debug` — inspect tab headers and template previews post-refresh.

## Command routing
- CoreOps reads `BOT_TAG`, `COREOPS_ENABLE_{TAGGED,GENERIC}_ALIASES`, and
  `COREOPS_ADMIN_BANG_ALLOWLIST`. Legacy `COMMAND_PREFIX` is unsupported and
  blocked in CI.

Doc last updated: 2025-10-27 (v0.9.7)
