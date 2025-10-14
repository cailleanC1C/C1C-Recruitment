# Phase 2 Findings

## Decisions
- Keep single Render service per environment; watchdog and scheduler stay co-resident.
- Config tab remains the canonical source for sheet-driven values; no inline JSON overrides.
- Allow-list enforcement happens before cog setup to prevent partial loads.

## Deferred to Phase 3
- Sheets ingestion refactor for recruitment search filters (requires new column mapping).
- Welcome automation to post dynamic attachments from Config tab metadata.

## Deferred to Phase 3b
- Extended CoreOps command set (`!env`, `!digest`, notification summaries).
- Cross-bot command bus; not required with current single-bot deployment.
- Granular logging levels per module (stays global until 3b instrumentation).
