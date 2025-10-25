# Guardrails — Overview

Guardrail captures store compliance evidence and automated scan outputs.

## Active Scopes
- [`command-prefix/`](command-prefix/) — Ensures no direct `COMMAND_PREFIX` usage leaks into the codebase.
- [`coreops-packaging/`](coreops-packaging/) — Tracks migration of CoreOps symbols into the supported package layout.

When adding a new guardrail scope, create a slug folder and drop dated reports inside.

Doc last updated: 2025-10-25 (v0.9.5)
