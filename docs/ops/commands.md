# CoreOps Help System

The help surfaces pull from the command matrix and cache registry to render consistent
copy across tiers. Use the following behavior notes when validating deploys or triaging
reports from staff and recruiters.

## `!help` — short index
- **Audience:** Admin-only shortcut; mirrors `!rec help` for the caller's tier.
- **Behavior:** Returns a compact embed grouped by tier with one-line blurbs only. The
  embed footer shows `Bot vX.Y.Z · CoreOps vA.B.C`; timestamps are no longer rendered.
- **Tip:** Trigger this after reloads to confirm the tier catalog hydrated from the live
  cache.

### Example (Admin tier excerpt)
```
Admin
- !config — Admin embed of the live registry with guild names and sheet linkage.
- !rec reload — Rebuild the config registry; optionally schedule a soft reboot.
```

## `!help <command>` — detailed view
- **Audience:** Any tier that can see the command in the short index.
- **Behavior:** Expands the command with the detailed copy from the Command Matrix,
  including a **Usage** line, prefix warning (commands accept `!rec` and admin bang
  aliases), and a contextual tip.
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
!rec refresh clansinfo
Usage: !rec refresh clansinfo
Tier: Staff (Recruiter role or higher required)
Detail: Refresh clan roster data when Sheets updates land.
Tip: Re-run if digest ages drift after clan merges.
```

### Example (User)
```
!rec ping
Usage: !rec ping
Tier: User
Detail: Report bot latency and shard status without hitting the cache.
Tip: Ask staff to escalate if latency exceeds 250 ms for more than 5 minutes.
```

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

### `!rec ping`

Prefix proxy for the admin ping command.

- **Access:** Admin (shares gating with the base `!ping` command)
- **Behavior:** Delegates to the hidden admin command that reacts with 🏓; used to confirm shard responsiveness.
- **Usage:** `!rec ping`
- **Notes:** Because the proxy invokes the admin command directly, non-admins still receive the “Admins only.” denial message.

Doc last updated: 2025-10-26 (v0.9.6)
