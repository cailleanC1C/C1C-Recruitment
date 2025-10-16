# Command Embed Conventions

## Shared footer builder
- Format: `Bot vX.Y.Z · CoreOps vA.B.C`.
- Optional context (e.g., source, environment) appends with ` • ` separators.

## Timestamp usage
- Use the embed timestamp for temporal context.
- Remove absolute dates/times from embed bodies and fields.

## Notes
- Reuse the shared footer helper in every CoreOps/admin command embed.
- Keep footer strings concise; avoid repeating information already visible in the embed.
