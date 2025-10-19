# CoreOps Development Notes — Phase 3 + 3b

## Telemetry helpers only
- Import telemetry data via `shared.coreops.cache_public` helpers (`get_snapshot`,
  `get_summary`, `refresh_now`).
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

---

_Doc last updated: 2025-10-20 (Phase 3 + 3b consolidation)_
