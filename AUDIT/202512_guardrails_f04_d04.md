# Guardrails Audit: F-04 and D-04 (sheet-backed toggles & docs README)

## Overview
This report audits the current implementations of guardrail checks **F-04** (documented feature toggles not referenced in code) and **D-04** (`docs/README.md` missing) to determine whether their recent failures are genuine or false positives in the present repository state.

## F-04 — Documented toggles not referenced in code

### Implementation location and behavior
- **File:** `scripts/ci/guardrails_suite.py`
- **Documented toggle source:** Fixed `DOCUMENTED_TOGGLES` set defined in the script, not read from docs or Sheets. 【F:scripts/ci/guardrails_suite.py†L21-L42】
- **Usage discovery:** `_extract_toggle_usage()` scans Python files for calls matching the regex `FeatureToggles.[^(]*\(\s*["'](?P<name>[A-Za-z0-9_]+)["']` and records line numbers for any captured toggle names. 【F:scripts/ci/guardrails_suite.py†L287-L300】
- **Scope of scan:** `_iter_python_files()` walks all `*.py` under `ROOT`, which is set to `Path(__file__).resolve().parents[1]` — resolving to the **`scripts/` directory**, not the repository root. AUDIT paths are skipped. 【F:scripts/ci/guardrails_suite.py†L21-L23】【F:scripts/ci/guardrails_suite.py†L70-L75】
- **Rule logic:**
  - F-01: toggles seen in code but absent from `DOCUMENTED_TOGGLES` → error.
  - F-04: toggles in `DOCUMENTED_TOGGLES` but not seen in the regex scan → warning. 【F:scripts/ci/guardrails_suite.py†L303-L315】

### Observations against current codebase
- Because `ROOT` points to `scripts/`, the regex scan never reaches runtime modules (e.g., `modules/`, `cogs/`), so any real toggle usage there is invisible to F-04.
- Runtime code reads toggles via the sheet-backed feature flag loader (e.g., `feature_flags.is_enabled("recruitment_welcome")`), not via `FeatureToggles.<method>("…")`, so the F-04 regex does not match actual usage patterns. 【F:modules/onboarding/watcher_welcome.py†L270-L293】【F:modules/common/runtime.py†L1109-L1138】

### Representative toggles from the current report

| toggle_name | where_defined | where_used_in_code | Notes |
| --- | --- | --- | --- |
| `recruitment_welcome` | Docs config + sheet FeatureToggles seed list. 【F:docs/ops/Config.md†L295-L322】 | Used in watcher gating and runtime module loading (`feature_flags.is_enabled`). 【F:modules/onboarding/watcher_welcome.py†L270-L293】【F:modules/common/runtime.py†L1109-L1147】 | Missed by F-04 because scan stops at `scripts/` and regex expects `FeatureToggles…` calls. |
| `housekeeping_keepalive` | Listed in guardrails `DOCUMENTED_TOGGLES`. 【F:scripts/ci/guardrails_suite.py†L33-L41】 | Scheduled via sheet toggle (`housekeeping_enabled`) and task name `housekeeping_keepalive`. 【F:modules/common/runtime.py†L1328-L1357】 | Regex/ROOT issues prevent detection; toggle naming differs (code uses `housekeeping_enabled` flag to enable the keepalive job). |
| `ENABLE_WELCOME_HOOK` | Guardrails documented toggle set; uppercase form in docs highlights. 【F:docs/ops/Config.md†L270-L325】【F:scripts/ci/guardrails_suite.py†L35-L38】 | No direct runtime string match; runtime uses lower-case `enable_welcome_hook` sheet flag. 【F:modules/onboarding/watcher_welcome.py†L270-L293】 | False positive: naming (case) and lookup method differ from guardrails regex expectations. |
| `ENABLE_PROMO_WATCHER` | Guardrails documented toggle set. 【F:scripts/ci/guardrails_suite.py†L36-L39】 | Runtime uses lower-case promo toggles (`promo_enabled` / `enable_promo_hook`) sourced from Sheets. 【F:modules/onboarding/watcher_welcome.py†L282-L293】 | Not matched because of naming mismatch and limited scan scope. |

### F-04 conclusions
- **Violations appear to be false positives.** Real feature toggles are sheet-backed and referenced via `feature_flags.is_enabled(...)` across runtime modules, but the guardrail scans only `scripts/` and only for `FeatureToggles.*("NAME")` patterns, so genuine usages are missed.
- **Conceptual misalignment:** The rule compares a hard-coded documentation list to string occurrences in code, ignoring the actual toggle source of truth (Sheets). A better target would be docs ↔ sheet schema/config (or the feature flag loader registry) instead of docs ↔ raw code strings.

## D-04 — docs/README.md missing

### Implementation location and behavior
- **File:** `scripts/ci/guardrails_suite.py`
- **Path resolution:** `ROOT = Path(__file__).resolve().parents[1]` → `scripts/`; `DOCS_ROOT = ROOT / "docs"` → `scripts/docs`. The check looks for `scripts/docs/README.md`. 【F:scripts/ci/guardrails_suite.py†L21-L24】【F:scripts/ci/guardrails_suite.py†L348-L352】
- **Check logic:** If `DOCS_ROOT / "README.md"` does not exist, emit D-04 error; otherwise continue to D-08 link coverage. 【F:scripts/ci/guardrails_suite.py†L348-L360】

### Comparison with repository layout
- The actual docs index lives at `docs/README.md` under the repository root and is present with correct casing. 【F:docs/README.md†L1-L20】
- Because `ROOT` resolves to `scripts/`, the guardrail looks in the non-existent `scripts/docs/README.md`, producing a spurious D-04 failure despite the real file existing at the repo root.

### D-04 conclusions
- The current D-04 failure is a **path-resolution false positive**: the check anchors to `scripts/` instead of the repository root, so it cannot see `docs/README.md`.
- A correct implementation should derive `ROOT` from the repository base (one level higher) and then check `ROOT / "docs" / "README.md"` with the exact filename casing already used in the repo.

## Next steps (no implementation in this PR)
- Retarget F-04 to compare documented toggles against the sheet-backed toggle registry (or Config/FeatureToggles schema) rather than regex-scanning code under `scripts/`.
- Expand the usage scan, if still needed, to operate from the repository root and to match `feature_flags.is_enabled("<toggle>")` patterns that reflect real runtime usage.
- Fix D-04 path resolution so it uses the repository root and the existing `docs/README.md` file.
- This PR is **audit-only**; no guardrail or runtime behavior has been changed.
