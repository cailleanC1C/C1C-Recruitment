# 📄 ADR-0021 — Reservations Sheet Adapter & Availability Recompute Helper

## Context

ADR-0020 established that clan availability must be derived from the manual
open-spot count in column **E** and structured reservations stored elsewhere,
with derived values written back to **AF/AH/AI** and the in-memory `bot_info`
cache updated immediately (Option A).

Implementing that strategy requires two new building blocks:

1. A reservations sheet adapter that can read/write the `RESERVATIONS_TAB`
   ledger, normalise rows, and expose active reservations per clan.
2. A reusable helper that recomputes availability for a single clan, writes the
   derived values back to `CLANS_TAB`, and mutates the cached clan row without a
   global cache flush.

## Decision

* Add a typed reservations adapter under `shared.sheets.reservations` that
  resolves configuration from the recruitment `Config` worksheet, normalises
  ledger rows, and exposes helpers to query and append reservations. The adapter
  also provides lightweight name-resolution utilities so callers can turn user
  IDs into display strings when generating reservation summaries.
* Implement `modules.recruitment.availability.recompute_clan_availability` as the
  single point of truth for availability derivation. The helper:
  1. Reads manual open spots (column **E**) for the requested clan.
  2. Counts active reservations from the adapter and optionally resolves holder
     names.
  3. Computes **AF = max(E − R, 0)**, **AH = R**, and **AI = "<R> -> names"**.
  4. Writes the derived values to `CLANS_TAB` via the Sheets async facade.
  5. Updates the cached clan row (and cache bucket) in-place—no global
     invalidation.

## Consequences

* Future features (`!reserve`, scheduled releases) can call the helper rather
  than duplicating sheet math or cache mutation logic.
* Cache coherence stays aligned with ADR-0020: clan panels observe the new
  availability immediately without triggering a refresh of the entire `clans`
  bucket.
* The reservations adapter centralises ledger parsing, making it easier to add
  validation or schema evolutions in later phases (PR-RES-02/03).

Doc last updated: 2025-11-13 (v0.9.8.2)
