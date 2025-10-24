# CoreOps Development Notes

## Telemetry helpers only
- Import telemetry data via `shared.coreops.cache_public` helpers (`list_buckets`,
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

## Testing commands
- `!rec refresh all` — verify cache warmers and actor logging.
- `!digest --debug` — confirm public telemetry includes age/next/retries.
- `!checksheet --debug` — inspect tab headers and template previews post-refresh.

Doc last updated: 2025-10-22 (v0.9.5)

CoreOps reads `BOT_TAG`, `COREOPS_ENABLE_{TAGGED,GENERIC}_ALIASES`, and `COREOPS_ADMIN_BANG_ALLOWLIST`. Legacy `COMMAND_PREFIX` is unsupported and blocked in CI.
