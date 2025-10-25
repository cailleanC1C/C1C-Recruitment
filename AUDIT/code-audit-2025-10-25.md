# C1C-Recruitment Code Audit — 2025-10-25

## Repository Summary (languages, folders, LOC rough order of magnitude)
- Primary implementation is Python 3.11+ (bot runtime, cogs, shared libraries, and CoreOps package). Representative entry points include `app.py`, `modules/common/runtime.py`, and `shared/sheets/*` (≈ tens of thousands of LOC across these packages).【F:app.py†L1-L116】【F:modules/common/runtime.py†L370-L516】【F:shared/sheets/recruitment.py†L1-L160】
- Supporting assets include JavaScript for deployment helpers and Render lane coordination, plus shell scripts for local/dev automation.【F:wait_render.js†L1-L12】【F:scripts/dev_run.sh†L1-L4】
- Documentation and CI live under `docs/` and `.github/`, with multiple Markdown runbooks and GitHub Actions workflows driving deployment and guardrails.【F:docs/ops/Config.md†L1-L35】【F:.github/workflows/render-deploy.yml†L1-L89】

## High-Risk Findings (Security & Data Loss)
1. **Production log channel fallback leaks cross-environment telemetry**  
   - **Severity:** High · **Confidence:** Medium  
   - The config loader hard-codes `LOG_CHANNEL_ID` to a production snowflake when the environment variable is absent. Any developer/staging bot that forgets to override the variable will start emitting log traffic (including operational metadata) to the live production channel.【F:shared/config.py†L68-L289】  
   - **What could go wrong:** Logs from non-production runs (which often contain debugging text, user identifiers, or partial secrets prior to sanitization) would post into the production guild, leaking data and confusing on-call responders.  
   - **How to test the fix:** In a staging environment, unset `LOG_CHANNEL_ID`, reload config, and assert that the bot refuses to send log messages (expect warning instead of contacting the production channel). Verify normal behavior resumes once a non-production ID is configured.

2. **Emoji proxy accepts plain HTTP downloads**  
   - **Severity:** High · **Confidence:** Medium  
   - The `/emoji-pad` route accepts both `http` and `https` schemes when proxying Discord CDN assets. Serving unencrypted responses opens the door to downgrade/MITM attacks because the proxy will happily republish whatever bytes were delivered.【F:shared/web_routes.py†L88-L147】  
   - **What could go wrong:** An on-path attacker could tamper with the proxied image (e.g., by injecting steganographic payloads or oversized files) that downstream Discord users consume as trusted operational assets.  
   - **How to test the fix:** Attempt to request an emoji via `http://cdn.discordapp.com/...` after tightening the scheme check; expect a 400 response. Confirm legitimate HTTPS requests continue to succeed and produce identical output.

## Reliability & Correctness Findings
1. **Sheets fetch blocks the event loop in recruiter search** (Severity: High · Confidence: High) — `_run_search` calls the synchronous `fetch_clans`, which ultimately performs Google Sheets I/O with blocking `time.sleep` retry loops. During cache misses this freezes the bot for the duration of the network call.【F:modules/recruitment/views/recruiter_panel.py†L714-L819】【F:shared/sheets/recruitment.py†L106-L150】【F:shared/sheets/core.py†L52-L123】  
2. **`scripts/dev_run.sh` mis-parses `.env`** (Severity: Medium · Confidence: High) — `export $(grep … | xargs)` explodes when values contain spaces, `#`, or quotes, leading to silent config drift for local developers.【F:scripts/dev_run.sh†L1-L4】  
3. **Health contract drift** (Severity: Medium · Confidence: Medium) — Runtime web server only exposes `/`, `/health`, `/healthz`, yet the shared health module and runbooks document `/ready` as the readiness endpoint, so automated probes or ops teams will misconfigure checks.【F:modules/common/runtime.py†L400-L425】【F:shared/health.py†L1-L63】  
4. **Docs parity script crashes** (Severity: Medium · Confidence: High) — `scripts/ci/check_docs.py` requires `docs/ops/.env.example`, but the file is absent, causing the guardrail job (and local `make docs-check`) to fail immediately.【F:scripts/ci/check_docs.py†L1-L82】【53bba1†L1-L3】

## Maintainability & Architecture Findings
- The config module’s production-only default (`LOG_CHANNEL_ID`) couples environments and requires institutional knowledge; better to fail closed or derive from a per-env template to avoid accidental cross-talk.【F:shared/config.py†L68-L289】  
- Documentation claims the deployment workflow cancels older runs via `wait_render.js`, but the current GitHub Action merely waits, leaving stale expectations for operators reviewing runbooks.【F:docs/contracts/core_infra.md†L76-L78】【F:.github/workflows/render-deploy.yml†L21-L89】

## Performance & Resource Usage Findings
- Blocking Sheets access in `_run_search` causes UI freezes whenever cache data expires or GSuite latency spikes. Wrapping the call in `asyncio.to_thread` or reusing the async cache loaders would keep the UI responsive.【F:modules/recruitment/views/recruiter_panel.py†L714-L819】【F:shared/sheets/core.py†L52-L123】

## Configuration & Secrets Hygiene
- `.env` template referenced throughout ops docs is missing, preventing new environments from discovering required keys and failing CI docs checks.【F:docs/ops/Config.md†L1-L35】【F:scripts/ci/check_docs.py†L1-L82】【53bba1†L1-L3】

## Logging, Telemetry & Observability
- Missing `/ready` route contradicts the documented contract, causing readiness dashboards to either probe `/healthz` (risking false negatives) or rely on `/` which is not formally documented.【F:modules/common/runtime.py†L400-L425】【F:shared/health.py†L1-L63】

## Concurrency, Async & Blocking I/O Risks
- Google Sheets helpers remain synchronous and are invoked directly inside async Discord handlers, blocking the event loop during retries and compounding latency under load.【F:modules/recruitment/views/recruiter_panel.py†L714-L819】【F:shared/sheets/recruitment.py†L106-L150】【F:shared/sheets/core.py†L52-L123】

## API/Integration Boundaries (rate limits, retries, error mapping)
- Sheets retry helper backs off without jitter and uses blocking sleeps; once moved off the event loop it should add jitter to avoid synchronized retries across multiple workers.【F:shared/sheets/core.py†L52-L123】

## Tests & Coverage (gaps, flaky patterns)
- Test suite barely exercises critical flows; e.g., `tests/test_health_contract.py` is a placeholder assertion, providing no coverage for watchdog, Sheets adapters, or recruiter panel logic.【F:tests/test_health_contract.py†L1-L2】

## CI/CD & Workflows (idempotency, queueing, caching, pinned versions)
- Render deploy workflow disables `cancel-in-progress`, conflicting with the documented “latest-wins with cancel” guarantee; older runs may continue deploying after a new commit lands.【F:.github/workflows/render-deploy.yml†L21-L89】【F:docs/contracts/core_infra.md†L76-L78】  
- Workflow re-initializes `npm` and reinstalls `node-fetch` on every run instead of caching dependencies, elongating queues (minor perf concern).【F:.github/workflows/render-deploy.yml†L37-L84】

## Docs & Versioning Drift (README, Architecture, ADRs, CHANGELOG consistency)
- Ops contract references the legacy cancel script while the code path changed, and readiness endpoints documented in shared modules don’t match the runtime implementation.【F:docs/contracts/core_infra.md†L76-L78】【F:shared/health.py†L1-L63】【F:modules/common/runtime.py†L400-L425】

## Quick Wins (Do Now, <30min each)
- [ ] Replace the `.env` loader in `scripts/dev_run.sh` with `set -a`/`source` semantics to preserve quoted values.【F:scripts/dev_run.sh†L1-L4】
- [ ] Restore a `/ready` handler in `modules/common/runtime.py` so probes align with the documented contract.【F:modules/common/runtime.py†L400-L425】【F:shared/health.py†L1-L63】
- [ ] Check in the missing `docs/ops/.env.example` template to unblock docs guardrail jobs.【F:scripts/ci/check_docs.py†L1-L82】【53bba1†L1-L3】

## Fix Plan (Prioritized Backlog)
1. **Stop defaulting logs to production channel** — *Severity: High · Effort: S · Suggested owner: CoreOps runtime team* — Require `LOG_CHANNEL_ID` to be explicitly provided per environment, default to “disabled” otherwise.【F:shared/config.py†L68-L289】
2. **Make recruiter Sheets access non-blocking** — *Severity: High · Effort: M · Suggested owner: Recruitment module maintainers* — Wrap synchronous fetches with `asyncio.to_thread` or refactor to reuse the async cache API, then exercise in regression tests.【F:modules/recruitment/views/recruiter_panel.py†L714-L819】【F:shared/sheets/core.py†L52-L123】
3. **Enforce HTTPS for emoji proxy** — *Severity: High · Effort: S · Suggested owner: Shared web utilities* — Restrict schemes to HTTPS and add defensive logging to trace rejected requests.【F:shared/web_routes.py†L88-L147】
4. **Restore `/ready` readiness contract** — *Severity: Medium · Effort: S · Suggested owner: CoreOps runtime team* — Register a `/ready` route in the aiohttp server and document the payload so ops dashboards remain consistent.【F:modules/common/runtime.py†L400-L425】【F:shared/health.py†L1-L63】
5. **Ship `.env` template + keep docs guardrails passing** — *Severity: Medium · Effort: S · Suggested owner: Docs tooling* — Add `docs/ops/.env.example` and wire docs CI to validate parity going forward.【F:scripts/ci/check_docs.py†L1-L82】【53bba1†L1-L3】
6. **Align Render deploy contract** — *Severity: Medium · Effort: M · Suggested owner: Infra/CI* — Either reintroduce the cancel-in-progress behavior (using `wait_render.js`) or update docs and monitoring to reflect “queue only” semantics.【F:.github/workflows/render-deploy.yml†L21-L89】【F:docs/contracts/core_infra.md†L76-L78】【F:wait_render.js†L1-L12】
7. **Expand automated tests** — *Severity: Medium · Effort: M · Suggested owner: QA/maintainers* — Build integration tests around the health server and recruiter panel to guard against regressions once async refactors land.【F:tests/test_health_contract.py†L1-L2】

## Proposed Patches (Unified Diffs)
```diff
diff --git a/modules/recruitment/views/recruiter_panel.py b/modules/recruitment/views/recruiter_panel.py
@@
-            try:
-                rows = recruitment_sheets.fetch_clans(force=False)
+            try:
+                rows = await asyncio.to_thread(
+                    recruitment_sheets.fetch_clans,
+                    force=False,
+                )
```
```diff
diff --git a/shared/web_routes.py b/shared/web_routes.py
@@
-        if parsed.scheme not in {"https", "http"} or parsed.hostname not in _ALLOWED_HOSTS:
+        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
             raise web.HTTPBadRequest(text="invalid source host")
```
```diff
diff --git a/scripts/dev_run.sh b/scripts/dev_run.sh
@@
-export $(grep -v '^#' .env 2>/dev/null | xargs) || true
+if [ -f .env ]; then
+    set -a
+    # shellcheck disable=SC1091
+    . ./.env
+    set +a
+fi
```
```diff
diff --git a/modules/common/runtime.py b/modules/common/runtime.py
@@
-        async def root(_: web.Request) -> web.Response:
+        async def root(_: web.Request) -> web.Response:
             payload = {
                 "ok": True,
                 "bot": get_bot_name(),
                 "env": get_env_name(),
                 "version": os.getenv("BOT_VERSION", "dev"),
             }
             return web.json_response(payload)
+
+        async def ready(_: web.Request) -> web.Response:
+            return web.json_response({"ok": True})
@@
-        app.router.add_get("/", root)
+        app.router.add_get("/", root)
+        app.router.add_get("/ready", ready)
         app.router.add_get("/health", health)
         app.router.add_get("/healthz", healthz)
```
```diff
diff --git a/docs/ops/.env.example b/docs/ops/.env.example
new file mode 100644
+DISCORD_TOKEN=
+ENV_NAME=dev
+BOT_NAME=C1C-Recruitment
+LOG_CHANNEL_ID=
+GSPREAD_CREDENTIALS=
+RECRUITMENT_SHEET_ID=
+ONBOARDING_SHEET_ID=
+WATCHDOG_CHECK_SEC=360
+WATCHDOG_STALL_SEC=
+WATCHDOG_DISCONNECT_GRACE_SEC=
+PUBLIC_BASE_URL=
+RENDER_EXTERNAL_URL=
```

## Follow-ups & Open Questions
- Should the emoji proxy also enforce host-specific TLS certificate pinning or additional MIME checks beyond the current content-type filter?【F:shared/web_routes.py†L88-L147】
- Are there remaining legacy call sites that still import synchronous Sheets helpers directly (outside recruiter panel) which also need `to_thread` shims?【F:shared/sheets/recruitment.py†L106-L150】
- Does infra prefer to revive `wait_render.js` cancellation semantics or update docs to the current “wait only” strategy? Confirmation will guide whether we clean up the unused script.【F:docs/contracts/core_infra.md†L76-L78】【F:.github/workflows/render-deploy.yml†L21-L89】【F:wait_render.js†L1-L12】
