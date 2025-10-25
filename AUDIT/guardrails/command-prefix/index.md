# Command Prefix Guardrail — Index

Use this folder to trace guardrail enforcement around the `COMMAND_PREFIX` usage.

| File | Purpose |
| --- | --- |
| `2025-10-23_command-prefix-scan.md` | Automated scan ensuring no stray `COMMAND_PREFIX` tokens ship in Python code. |

## Notes
- Regenerate the scan via `scripts/audit_command_prefix_usage.py`.
- Link incidents or diagnostics that trigger follow-up work back to this index for
  discoverability.

Doc last updated: 2025-10-25 (v0.9.5)
