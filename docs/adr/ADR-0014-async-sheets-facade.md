# ADR-0014 — Async Sheets Facade for Event-Loop Safety
Date: 2025-10-25

## Context
Synchronous Google Sheets helpers were invoked from async handlers, causing
event-loop blocking (audit finding). Retries used blocking sleeps.

## Decision
Adopt `shared/sheets/async_facade.py` as the sole import path for Sheets access
in async code. The facade executes sync client work via `asyncio.to_thread`.
Update all async call sites to use the facade.

## Consequences
- UI responsiveness preserved; no blocking I/O on the event loop.
- Slight overhead per call due to thread scheduling.
- Sync scripts keep using sync helpers; async code uses the facade uniformly.

## Status
Accepted


Doc last updated: 2025-10-25 (v0.9.5)
