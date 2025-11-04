# Agents Registry

> Single source of truth for all non-human actors (bots, service accounts, webhooks, schedulers).  
> Store **secret names only** (ENV var keys), never values. Update this file in the same PR as any permission/scope change.

---

## 1) Directory

| Agent | Type | Primary Purpose | Environments | Owner | Notes |
|---|---|---|---|---|---|
| The Woadkeeper | Discord Bot (discord.py) | Recruitment, onboarding, ops | prod, test | Caillean | Unified bot; replaces legacy modules |
| Google Sheets SA | Service Account | Sheets R/W (config, toggles, reports) | prod, test | Caillean | Least-privilege per sheet |
| Ticket Tool (external) | External Bot | Ticket threads (welcome flow) | prod | 3rd party | Thread owner in private tickets |

---

## 2) The Woadkeeper (Discord Bot)

**Identifiers**
- App / Client ID: `${DISCORD_APP_ID}`
- Public Bot User ID: `${DISCORD_BOT_USER_ID}`

**Secrets (ENV var names)**
- `DISCORD_BOT_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON` (path or inline JSON)
- `SHEETS_RECRUITMENT_SPREADSHEET_ID`
- `SHEETS_CONFIG_SPREADSHEET_ID`

**Gateway Intents (portal + code)**
- `GUILD_MEMBERS` (limited; role checks only)
- `GUILD_MESSAGE_REACTIONS` (emoji triggers)
- `GUILD_MESSAGES`
- `MESSAGE_CONTENT` (feature-gated; minimum scope)

**OAuth2 Scopes**
- `bot`, `applications.commands`

**Required Discord Permissions (server)**
- Send Messages in Threads
- Add Reactions
- Read Message History
- Use Slash Commands
- Manage Messages (bot-ops channels only)

**RBAC / Access Lists**
- Config JSON: `config/bot_access_lists.json` (IDs only; numeric; comma-separated, no spaces)
- `options.threads_default: true` (inherit channel allow-list)

**Feature Toggles (Sheets-only)**
- Sheet/table: `FeatureToggles!A:B`
- Examples: `WELCOME_FLOW_ENABLED`, `HELP_DYNAMIC_RENDER`, `SIEGE_REPORTS_ENABLED`
- Principle: **Do not** read toggles from ENV.

**Logging / Lifecycle**
- Log channel ID: `${LOG_CHANNEL_ID}`
- Dedupe window: `5s`
- Watchers: lifecycle only (no duplicate embed logs)

**Deploy / Runtime**
- Host: Render
- Env groups: `prod`, `test`
- Health pings: minimal (per governance)

---

## 3) Google Sheets Service Account

**Identity**
- Service account email: `${GOOGLE_SA_EMAIL}`

**Secrets (ENV var names)**
- `GOOGLE_SERVICE_ACCOUNT_JSON`

**Access**
- Read/Write: Recruitment, Config, FeatureToggles
- Read-only: Audit/Reports (if present)
- Document IDs come from ENV or Sheet Config:
  - `SHEETS_RECRUITMENT_SPREADSHEET_ID`
  - `SHEETS_CONFIG_SPREADSHEET_ID`

**Principles**
- No hard-coded tab names; resolve via Sheet Config.
- Least privilege; separate prod/test shares.

---

## 4) Webhooks / Schedulers (if used)

| Name | Kind | Purpose | Endpoint / ID | Secret (ENV) | Notes |
|---|---|---|---|---|---|
| Ops Webhook | Discord webhook | Guardrails/ops summaries | `${OPS_WEBHOOK_URL}` | `OPS_WEBHOOK_URL` | Optional

---

## 5) Guardrails & Change Control

- Any change to **intents, OAuth scopes, permissions, or access lists** must:
  1) Be reflected here,  
  2) Include a short rationale in the PR body,  
  3) Update CI/Guardrails config if needed.
- Don’t invent labels; follow `.github/labels/labels.json`.
- **AUDIT** folder is excluded from tests/analysis (except for output artifacts).

---

## 6) Codex Hook (read this, don’t duplicate policy)

For PR formatting rules, labels, doc footers, and logging standards, see **CollaborationContract.md — Appendix A (Codex Operating Standards)**.  
This file only tracks agents and their permissions.

---

## 7) Validation Checklist (used by Codex)

- [ ] Bot IDs and ENV var names exist (no secret values in repo).
- [ ] Intents listed match portal + code.
- [ ] Feature toggles read from **Sheets**, not ENV.
- [ ] `config/bot_access_lists.json` present; IDs are numeric; `threads_default` set appropriately.
- [ ] Log channel ID present.
- [ ] This file updated in the same PR as any scope/permission change.

---

Doc last updated: 2025-11-04 (v0.9.7)
