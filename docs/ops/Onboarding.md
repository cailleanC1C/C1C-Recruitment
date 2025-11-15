# Onboarding

## Config keys
| Key | Source | Notes |
| --- | --- | --- |
| `ONBOARDING_SHEET_ID` | Environment | Sheet identifier for the onboarding workbook (separate from recruitment). |
| `ONBOARDING_TAB` | Onboarding Config sheet | Tab name for the onboarding questions worksheet. Preloaded at startup and refreshed weekly; required headers: `flow, order, qid, label, type, required, maxlen, validate, help, note, rules`. |

## Notes
- The onboarding questions cache preloads during startup alongside `clans`, `templates`, and `clan_tags`.
- A scheduled refresh runs weekly via the cache scheduler (`interval=7d`).
- The onboarding sheet ID resolves strictly from `ONBOARDING_SHEET_ID`; legacy fallbacks are disabled.

## Troubleshooting
- `missing config key: ONBOARDING_TAB` — Sheet configuration does not provide the tab name. Update the Config sheet and rerun the refresh. (Alias `onboarding.questions_tab` is no longer accepted.)
- `onboarding_questions cache is empty (should be preloaded)` — Startup preload failed or returned zero rows. Fix the sheet and rerun the cache refresh (`!ops refresh onboarding_questions`).

## Lifecycle & Single-Message Policy

The onboarding wizard lives in **one panel message** inside the ticket thread.
All user-visible updates **edit that same message**. The wizard does not post
additional messages for state changes.

Component handlers use a single acknowledgment path (`defer_update`) and route
through one controller render pipeline to avoid duplicate edits or red toasts.

Persistent views for the onboarding UI are **registered after the bot is ready**
so components remain active across restarts.

## UI Mockups (Inputs v1)

> Use the buttons below. Don’t type answers as messages—those won’t be read.

### Text (short)
**What’s your in-game name?** *(required)*  
_Use your exact player name so we can find you easily._  
💬 Current answer: —  
Buttons: `[Answer ✏️]  [Next ➡️]  [Cancel ❌]` *(Next disabled until answered)*

### Number
**What’s your current player power?** *(required)*  
_Hints/examples come from the sheet `help` cell if provided._  
💬 Current answer: —  
Buttons: `[Answer 🔢]  [Back ⬅️]  [Next ➡️]  [Cancel ❌]`

### Paragraph (optional)
**How would you describe your playstyle?** *(optional)*  
_Help comes from the sheet. No invented examples._  
💬 Current answer: —  
Buttons: `[Answer 💬]  [Skip ⏭️]  [Back ⬅️]  [Next ➡️]  [Cancel ❌]`

### Boolean
**Are you interested in participating in Siege?** *(required)*
Buttons: `[✅ Yes]  [❌ No]  [Back ⬅️]  [Next ➡️]  [Cancel ❌]`

> All prompt text, help, validation, and limits are sheet-driven. If a cell is blank, the UI shows nothing (no fallback examples).

### Single-select
**Pick the option that matches your stage best.** *(required)*  
_Values come from the sheet `values` cell; order preserved._  
🎯 Selected: —  
Controls: a dropdown with the listed values.  
Buttons: `[Back ⬅️]  [Next ➡️]  [Cancel ❌]` *(Next disabled until selected)*

### Multi-select
**Which Hydra difficulties are you currently hitting?** *(optional)*  
_Values come from the sheet; we do not invent examples._  
🎯 Selected: —  
Controls: a dropdown that allows multiple selections (max = number of values).  
Buttons: `[Skip ⏭️]  [Back ⬅️]  [Next ➡️]  [Cancel ❌]`

> Resume: previously chosen options render pre-selected; users can change and continue later.

## Summary & Finish Step
When the last question is answered, the wizard shows a **Finish ✅** button.
Clicking it posts a final embed to the thread:

> <@&RecruitmentCoordinator> New onboarding submission ready.
>
> **🎉 Welcome Summary**
> **IGN**<br>
> Caillean<br>
>
> **Player Power**<br>
> 3 100 000<br>
>
> **Playstyle**<br>
> Focused but chill — enjoys teamwork and slow progression.<br>
>
> **Stage**<br>
> Early Game<br>
>
> **Hydra Difficulties**<br>
> Hard, Brutal<br>
>
> **Interested in Siege?**<br>
> Yes<br>
>
> 🕓 Completed • Nov 8 2025 | Total Questions Answered: 6
>
> All paragraph answers are shown in full (≤ 300 chars each; ≤ 1020 combined).
> Recruiter ping is controlled by sheet toggle.
> Completed sessions cannot restart.
> Footer includes the UTC completion timestamp and total answered count.

## Resume & Recovery

- Sessions persist to the onboarding sheet (`OnboardingSessions` tab) so applicants can pause and return later.
- The panel shows a **Resume** button when a saved session exists. **Open questions** also resumes automatically.
- If the bound panel message is missing, the bot recreates it and binds the restored session to the new message.
- Recruiters with **Manage Threads** can run `!onb resume @user` inside the onboarding ticket thread to recover the panel for that user.
- Finished sessions are immutable — post-finish clicks display a "session closed" notice without changing data.

Doc last updated: 2025-11-20 (v0.9.7)
