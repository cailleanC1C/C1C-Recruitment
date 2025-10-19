# ADR-0001 — Sheets Access Layer (Async + Cached)

- Date: 2025-10-20

## Context

Phase 3 introduced a shared asynchronous cache to make Google Sheets access non-blocking across the deployment. Phase 3b expanded the layer to expose telemetry consumed by CoreOps without leaking internal details.

## Decision

- All Sheets calls must go through `shared/sheets/cache_service.py`.
- Caches preload on worker boot (preloader) and refresh asynchronously via the scheduler.
- The public API surface is limited to telemetry-safe helpers such as `get_snapshot()`, `refresh_now()`, and `get_summary()`.
- Hot paths never await direct Sheets I/O operations.

## Consequences

Adopting the shared cache delivers predictable latency while ensuring a single telemetry source for Sheets usage and refresh health. Public helpers make it safe to expose cache data to embeds without reaching into private state.

## Status

Accepted — 2025-10-20
