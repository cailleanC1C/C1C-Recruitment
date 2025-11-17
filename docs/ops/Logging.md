# Logging

Humanized Discord logs keep operators informed without duplicating the structured
JSON logs already written to stdout. Style, emoji selection, and formatting rules
now live in [`docs/_meta/DocStyle.md`](../_meta/DocStyle.md); this file focuses on
configuration, helper wiring, and runtime policy.

## Destinations & configuration
- **Channel:** `LOG_CHANNEL_ID` controls which channel receives the humanized
  feed. The same ID must appear in `.env.example` and Render’s environment.
- **Verbosity:** `LOG_LEVEL` determines which structured messages reach stdout.
  Discord posts always use the curated templates regardless of level.
- **Identity:** `BOT_NAME`, `BOT_VERSION`, and `ENV_NAME` populate log titles and
  footers so operators know which deployment emitted each line.
- **Transport:** All log posts route through the CoreOps cog and inherit the
  thread/channel context of the configured destination.

## Template helpers
- Templates live in `shared/logfmt.LogTemplates` and are consumed by the Welcome,
  CoreOps, and scheduler modules.
- New templates must follow the DocStyle guide before being added here.
- Logging helpers only rely on cached Discord objects; never issue `fetch_*`
  calls purely for logging purposes.

## Dedupe policy
- Window: fixed at 5 seconds. All dedupe is in-memory and process-local.
- Keys:
  - Refresh summaries: `refresh:{scope}:{snapshot_id}` (snapshot ID optional;
    falls back to a timestamp bucket hash of the bucket list).
  - Welcome summaries: `welcome:{tag}:{recruit_id}` (recruit ID falls back to
    `0` when unavailable).
  - Permission sync: `permsync:{guild_id}:{ts_bucket}` where `ts_bucket` is
    derived from the dedupe window.
- Within the window, only the first event is emitted; later duplicates are
  ignored to keep the Discord channel readable.

## Configuration knobs
No runtime environment flags affect logging templates. Numeric snowflake IDs stay
hidden, and refresh summaries always use the concise inline layout.

## Operational rules
- Do not call Discord `fetch_*` APIs purely for logging; the helpers rely on
  cached objects and gracefully degrade to `#unknown` placeholders.
- Continue emitting structured logs (JSON/stdout) for auditability—only the
  human-facing Discord posts use the templates above.
- The watchtower (scheduler/watchdog) modules treat log posting failures as
  retryable errors and will raise alerts if the ops channel becomes unavailable.

Doc last updated: 2025-11-17 (v0.9.7)
