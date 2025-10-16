# Redaction & Masking Policy

## Secrets in embeds
- Secrets render with `(masked)` appended and only the final four characters visible.
- Grouped sections highlight which values are masked without exposing raw tokens.

## Log safeguards
- High-sensitivity keys (e.g., `SERVICE_ACCOUNT_JSON`, OAuth credentials) never appear in embeds or logs.
- Runtime logging strips or replaces any value flagged as a secret before emission.
