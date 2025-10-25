# ADR-0015 — Config Hygiene & Secrets Handling
Date: 2025-10-25

## Context
Audit identified medium-severity drift: missing `.env.example` parity, unclear required vs optional envs, and risk of accidental token leakage.

## Decision
1. Enforce required keys at import (`DISCORD_TOKEN`, `GSPREAD_CREDENTIALS`, `RECRUITMENT_SHEET_ID`) — fail fast with a clear error.
2. Keep optional keys truly optional; log a single startup warning when omitted (e.g., `LOG_CHANNEL_ID` disables Discord log posting).
3. Add CI guardrails to ensure `.env.example` matches `docs/ops/Config.md` and scan for obvious Discord token patterns.

## Consequences
- Deterministic startup: misconfigurations surface early with explicit messages.
- Docs and examples remain synchronized by automation.
- Reduced risk of committing a live token; lightweight scan enforces hygiene.

## Status
Accepted

## Verification
- Boot without one required key → process exits with clear error.
- Boot with all required keys but without `LOG_CHANNEL_ID` → warning once; bot runs.
- CI parity check fails if docs and `.env.example` diverge; leak scan fails on Discord token patterns.
