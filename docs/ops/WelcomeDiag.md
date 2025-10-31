# Welcome Flow Diagnostics

The welcome panel temporarily exposes additional instrumentation to isolate view timeout
and interaction acknowledgement issues. Enable diagnostics in environments where the
welcome flow should emit granular traces and JSONL snapshots.

## Enabling diagnostics

Set the environment variable `WELCOME_DIAG=1` before starting the bot. When the flag is
absent or set to `0`, all instrumentation remains silent and the bot behaves as normal.

```
export WELCOME_DIAG=1
```

## Outputs

- Human-readable logs are routed through the existing welcome log channel with extra
  diagnostic fields.
- Structured events append to `AUDIT/welcome_flow_diag.jsonl`. The summarizer workflow
  consumes this file to produce the PR Findings comment.

## Toggling off

Unset `WELCOME_DIAG` or restart the bot without the flag to disable the instrumentation.
All additional logging paths become inactive when the flag is off.

Doc last updated: 2025-10-31 (v0.9.7)
