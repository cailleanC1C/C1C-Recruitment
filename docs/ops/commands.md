# CoreOps Help System

The help surfaces pull from the command matrix and cache registry to render consistent
copy across tiers. Use the following behavior notes when validating deploys or triaging
reports from staff and recruiters. Command copy and usage strings should originate from
[`../_meta/COMMAND_METADATA.md`](../_meta/COMMAND_METADATA.md); update that export first, then
mirror the changes here and in the matrix to keep a single source of truth.

> **Style reference:** Logging, embed, and help text conventions are centralized in
> [`docs/_meta/DocStyle.md`](../_meta/DocStyle.md). This runbook only documents the
> layout and runtime behavior for each help surface.

## `@Bot help` — overview layout
- **Audience:** Everyone; the embed set filters to the caller’s access tier.
- **Behavior:** Sends one message containing four embeds in fixed order:
  1. **Overview** — long-form description reused verbatim from the legacy help copy.
  2. **Admin / Operational** — Config & Health, Sheets & Cache, Permissions, Utilities, Welcome Templates.
  3. **Staff** — Recruitment, Sheet Tools, Milestones.
  4. **User** — Recruitment, Milestones, General (includes `@Bot help` and `@Bot ping`).
- **Empty sections:** Hidden by default; set `SHOW_EMPTY_SECTIONS=true` to render a
  “Coming soon” placeholder.
- **Footer:** Uses the standard version line defined in `DocStyle.md`.
- **Tip:** Trigger this after reloads to confirm the tier catalog hydrated from the live
  cache.

### Example (Admin embed excerpt)
```
Admin / Operational — Config & Health
• !ops env — Staff snapshot of environment name, guild IDs, and sheet linkage.
• !ops health — Inspect cache/watchdog telemetry pulled from the public API.
```

## `@Bot help <command>` — detailed view
- **Audience:** Any tier that can see the command in the short index.
- **Behavior:** Expands the command with the detailed copy from the Command Matrix,
  including a **Usage** line and contextual tip.
- **Footer:** Standard version-only line per `DocStyle.md`; embeds omit timestamps to match the audit policy.
- **Reminder:** The detailed embed highlights when the caller lacks the required tier.

### Example (Admin)
```
!checksheet
Usage: !checksheet [--debug]
Tier: Admin (CoreOps)
Detail: Validate Sheets tabs, named ranges, and headers using public telemetry.
Tip: Run after registry edits or onboarding template changes.
```

### Example (Recruiter / Staff)
```
!ops refresh clansinfo
Usage: !ops refresh clansinfo
Tier: Staff (Recruiter role or higher required)
Detail: Refresh clan roster data when Sheets updates land.
Tip: Re-run if digest ages drift after clan merges.
```

### Example (User)
```
@Bot ping
Usage: @Bot ping
Tier: User
Detail: Report bot latency and shard status without hitting the cache.
Tip: Ask staff to escalate if latency exceeds 250 ms for more than 5 minutes.
```

## CoreOps / Admin Commands

### `!cfg [KEY]`
Read-only admin snapshot of a merged config key and the tail of the source sheet ID.

- **Audience:** Admin / Bot Ops (requires `administrator` permission)
- **Usage:** `!cfg [KEY]` (defaults to `ONBOARDING_TAB` when omitted)
- **Behavior:** Replies with the resolved value, originating sheet tail, and total merged-key count so ops can confirm reloads.
- **Tip:** Keys are case-sensitive and should match the Config tab headers; the sheet ID tail is redacted automatically.

## Recruitment commands alignment

### !clan `<tag>`

Shows a clan’s profile and entry-criteria card.

- **Access:** Public (no role restrictions)
- **Behavior:** Posts in-channel. Displays the **Profile** card (with crest), adds 💡 reaction to toggle between Profile and Entry Criteria.
- **Usage:** `!clan C1CE`
- **Error Handling:** If tag not found, returns a small red embed.
- **Feature Toggle:** `clan_profile`

### !clansearch

Launches the member-facing search panel.

- **Access:** Public (no role restrictions)
- **Behavior:** Opens an interactive panel that edits its own message whenever filters change so channels do not fill with duplicates.
- **Usage:** `!clansearch`
- **Feature Toggle:** `member_panel`

### !clanmatch

Opens the text-only recruiter panel for filtering and matching clans.

- **Access:** Staff / Recruiters
- **Behavior:** Interactive panel, text-only for speed and mobile usability.
- **Layout:** Panel controls stay within Discord’s 5-row limit (4 selects + 1 button row); pagination buttons live on the separate results message.
- **Usage:** `!clanmatch`
- **Feature Toggle:** `recruiter_panel`

### !welcome `[clan] @mention`

Posts the cached welcome template for the provided clan tag.

- **Access:** Staff / Admin
- **Behavior:** Pulls templates via `shared.sheets` cache; appends any additional note supplied after the mention.
- **Usage:** `!welcome C1CE @Player`
- **Feature Toggle:** `recruitment_welcome`

### `!onb resume @member`
Recruiter-only recovery command for onboarding ticket threads.

- **Audience:** Recruiters / Staff with `Manage Threads`
- **Usage:** `!onb resume @member` (run inside the recruit’s onboarding thread)
- **Behavior:** Validates thread context, reconnects to the onboarding wizard, and restores the saved panel (posting a replacement message when needed).
- **Error handling:** Responds with guidance when invoked outside a thread, when no matching session exists, or when the onboarding controller is offline.

### `@Bot ping`

Mention-style health check.

- **Access:** Anyone who can see the bot.
- **Behavior:** Invokes the prefix proxy and reacts with 🏓 so the caller knows the shard is alive.
- **Usage:** `@Bot ping`
- **Notes:** Admins still have access to the hidden `!ping` reaction command; the mention route keeps user help consistent.

Doc last updated: 2025-11-17 (v0.9.7)
