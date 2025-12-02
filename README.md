<!-- Keep README user-facing -->
<!-- Dev layout reference: recruitment modules now live in modules/recruitment/, -->
<!-- shared sheet adapters consolidate under shared/sheets/. See docs/Architecture.md. -->
# C1C Bot — The Woadkeeper
Version v0.9.8.2

Welcome, traveller of the Blue Flame.  
The Woadkeeper keeps our clans organised, our newcomers guided, and our Sheets clean.  
Think of it as the cluster’s quiet little helper: always awake, always watching, and always keeping the halls tidy so people can focus on playing and having fun.
## Role overview
- **Users** get quick answers about clans and bot status without pinging staff.
- **Staff** use richer panels with more info to clans needs and ready-to-send welcome messages.
- **Admins** keep the bot running smoothly and coordinate anything that touches the Ops toolkit.
# 🌟 What the Woadkeeper Does
### For normal users
- `@<Botname> help` — lists everything you can access with a short tip for each item.
- **Find a clan**
  `!clan <tag>` gives you a clean profile card with requirements, crest, and quick notes.
- **Browse the cluster**
  Use `!clansearch` to open the interactive search menu.
- **Track your shard mercy**
  `!shards` opens your personal shard tracker panel in a private thread. It shows stash, mercy counters, last pulls, and base chances for Ancient, Void, Sacred, and Primal shards, including the split Legendary/Mythical path for Primals.
- **Answer onboarding prompts**
  When the onboarding wizard in your welcome thread says “Input is required,” reply in that same thread with your answer. The bot captures your message directly—no extra “Enter answer” button needed—and enables **Next** once it validates the reply.
- **Check the bot**
  `@BotName ping` — answers with 🏓 if all systems are up.
The bot only shows commands you can actually run; if you need more tools, ask an admin to review your roles.
### For staff & recruiters
Staff can use all user commands plus:
- **Recruitment panel**  
  `!clanmatch` opens the matching tool to help place new members.
- **Welcome Messages**  
  `!welcome [clan] @name` posts the welcome and logs it in the right places.
Operational commands (anything that peeks under the hood of the bot like refresh buttons, sync helpers and similar tools) live in the Ops docs. Start with the [Command Matrix](docs/ops/CommandMatrix.md) and [Perm Command Quickstart](docs/ops/PermCommandQuickstart.md) to see what each command does before you press go.
### Admin snapshot
Admins handle the bigger picture:
- Caches staying fresh  
- Sheets staying clean  
- Reservation ledger behaving  
- Permissions syncing properly  
- Onboarding running without stalling  
Start with:
- **Ops Runbook:** `docs/Runbook.md`
- **Troubleshooting:** `docs/Troubleshooting.md`
- **Ops Command Matrix:** `docs/ops/CommandMatrix.md`
- **Watchers Reference:** `docs/ops/Watchers.md`
- **Cluster Role Map:** `!whoweare` prints the live "Who We Are" roster straight from the WhoWeAre sheet so cluster leads can see who holds which roles (with snark) in real time.

This is your Swiss-army knife for keeping the bot healthy.
# 🧭 Behind the Curtain — How It Works
If you’re curious how the bot thinks, check:
- **Architecture Overview:** `docs/Architecture.md`  
- **Module docs:**  
  - `docs/modules/Onboarding.md`  
  - `docs/modules/Welcome.md`  
  - `docs/modules/Recruitment.md`  
  - `docs/modules/Placement.md`  
  - `docs/modules/CoreOps.md`  
  - `docs/modules/PermissionsSync.md`
    
Each module doc explains what that subsystem does and how it fits into the bigger picture.
# 📚 Quick Documentation Links
- 🏛 **Architecture:** `docs/Architecture.md`  
- 📘 **Ops Runbook:** `docs/Runbook.md`  
- 🔧 **Command Matrix:** `docs/ops/CommandMatrix.md`  
- 🛠 **Troubleshooting:** `docs/Troubleshooting.md`  
- 🔭 **Watchers:** `docs/ops/Watchers.md`  
- 🧩 **Modules:** in `docs/modules/`  
- 📜 **Contributor & Dev Docs:**
  - `docs/_meta/DocStyle.md`
  - `docs/contracts/CollaborationContract.md`
  - ADRs in `docs/adr/`

Doc last updated: 2025-12-01 (v0.9.8.2)
