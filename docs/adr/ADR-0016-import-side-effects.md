# ADR-0016 — Remove Import-Time Config Side Effects
Date: 2025-10-25

## Context
Strict env validation (PR6) is correct but importing `c1c_coreops` during Docker build failed because package import transitively loaded `shared.config` at module import-time.

## Decision
Avoid importing runtime-bound modules from package `__init__`. Move `shared.config` access into runtime boot functions (e.g., `setup()`), preserving strict validation at startup.

## Consequences
- Docker build can import packages without secrets.
- Strict validation remains enforced at runtime boot; misconfigurations still fail fast.
- Clear boundary: libraries remain import-safe; apps validate on start.
- Selected top-level re-exports are preserved via lazy ``__getattr__`` proxies; no eager imports occur.

## Status
Accepted

## Verification
Docker build succeeds (import `c1c_coreops` OK) with no env provided.

Runtime boot still fails fast when required env is missing (because `shared.config` is imported during startup).

Test suite passes in CI.


Doc last updated: 2025-10-26 (v0.9.6)
