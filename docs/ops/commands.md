# CoreOps Help System

The help surfaces pull from the command matrix and cache registry to render consistent
copy across tiers. Use the following behavior notes when validating deploys or triaging
reports from staff and recruiters. Command copy and usage strings should originate from
[`../_meta/COMMAND_METADATA.md`](../_meta/COMMAND_METADATA.md); update that export first, then
mirror the changes here and in the matrix to keep a single source of truth.

## `@Bot help` — overview layout
- **Audience:** Everyone; the embed set filters to the caller’s access tier.
- **Behavior:** Sends one message containing four embeds in fixed order:
  1. **Overview** — long-form description reused verbatim from the legacy help copy.
  2. **Admin / Operational** — Config & Health, Sheets & Cache, Permissions, Utilities, Welcome Templates.
  3. **Staff** — Recruitment, Sheet Tools, Milestones.
  4. **User** — Recruitment, Milestones, General (includes `@Bot help` and `@Bot ping`).
- **Empty sections:** Hidden by default; set `SHOW_EMPTY_SECTIONS=true` to render a
  “Coming soon” placeholder.
- **Footer:** `Bot vX.Y.Z · CoreOps vA.B.C • For details: @Bot help` on every embed.
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
- **Footer:** Version info only; embeds omit timestamps to match the new audit policy.
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

### `!cfg <KEY>`
Shows the current value for a single onboarding or recruitment config key and where it originated.

- **Permission:** Admin only
- **Usage:** `!cfg ONBOARDING_TAB`
- **Example Response:** `🧩 Config — key=ONBOARDING_TAB • value=OnboardingQuestions • source=sheet:…Qdnb2I`

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

### `@Bot ping`

Mention-style health check.

- **Access:** Anyone who can see the bot.
- **Behavior:** Invokes the prefix proxy and reacts with 🏓 so the caller knows the shard is alive.
- **Usage:** `@Bot ping`
- **Notes:** Admins still have access to the hidden `!ping` reaction command; the mention route keeps user help consistent.

Doc last updated: 2025-11-07 (v0.9.7)
