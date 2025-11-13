# 📄 ADR-0020 — Availability Derivation (E → AF/AH/AI) & Cache Update Strategy
## **Context**
Clan availability was previously maintained manually (column E or AF) with no differentiation between ingame open spots and reserved seats.
Panels, reports, and onboarding logic all depend heavily on accurate seat counts.
Reservation introduction creates a new responsibility: ensuring that AF (effective availability) remains correct and up-to-date at all times.
Additionally, the bot uses a cache layer for Sheets data (bucket: `bot_info`).
Without careful synchronization, reservations could lead to temporary cache staleness and incorrect panel output.
## **Decision**
### 1. Column Semantics in `CLANS_TAB` (bot_info)
For each clan:
* **E** (manual):
  Ingame open spots (maintained exclusively by humans).
  This is the *authoritative* SSoT for ingame availability.
* **R** (derived):
  Count of active reservations for that clan from `RESERVATIONS_TAB`.
The bot derives:
* **AH = R**
* **AF = max(E − R, 0)**
* **AI = "<R> -> username1, username2, …"`
Only `E` remains human-editable.
`AF`, `AH`, and `AI` are *always* rewritten by the bot based on `E + reservations`.
### 2. Where availability is used
All panels and reports continue to use:
* **AF** = effective available seats
This ensures no behavioural change for recruiters or members; only the internal data derivation is improved.
### 3. Cache Update Strategy (“Option A”)
To ensure panels reflect changes immediately without global cache resets:
* Whenever a reservation changes state (create / expire / future manual release), the bot:
  1. Writes updated AH/AF/AI to `CLANS_TAB`
  2. Immediately updates the **in-memory cache entry** for that **specific clan** in `bot_info`
No global cache purge is performed.
This yields:
* Instant panel correctness
* Minimal API calls
* Full consistency between sheet and cache
* No interference with other buckets or scheduled sheet loads
## **Consequences**
* Panels and reports are always up-to-date.
* No waiting for scheduled refreshes.
* Reduced risk of showing outdated open slots.
* Bot logic must centralize clan-row updates to ensure cache mutation is consistent.
* Future commands that modify seats/reservations will reuse this strategy.

Doc last updated: 2025-11-13 (v0.9.7)
