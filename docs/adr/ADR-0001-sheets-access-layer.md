# ADR-0001 — Sheets Access Layer (Async + Cached)

- Date: 2025-10-18

## Context

Phase 3 introduced a shared asynchronous cache to make Google Sheets access non-blocking across the deployment. The goal was to provide deterministic response times while consolidating telemetry for all Sheets interactions.

## Decision

- All Sheets calls must go through `shared/sheets/cache_service.py`.
- Caches preload on worker boot and refresh asynchronously.
- The public API surface remains limited to `capabilities()`, `refresh_now()`, `get_ttl()`, and `get_age()`.
- Hot paths never await direct Sheets I/O operations.

## Consequences

Adopting the shared cache delivers predictable latency while ensuring a single telemetry source for Sheets usage and refresh health.

## Status

Accepted — 2025-10-18
