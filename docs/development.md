# Development

## Setup
- Install Python 3.12.
- Create a Discord application and bot token with the required intents.
- Export the following environment variable before running locally:

```text
DISCORD_TOKEN=<bot token>
```

- Enable the **Message Content Intent** so the bot can read command prefixes.
- Enable the **Server Members Intent** so RBAC checks receive member roles.

## Run locally
Install dependencies and start the bot:

```bash
pip install -r requirements.txt
python app.py
```

## Try the prefixes
Use both styles to confirm parsing:

```text
!rec ping
@C1C Recruitment help
```

## Project layout
- Core cogs live in `modules/`. CoreOps is loaded via `modules.coreops`.
- Shared helpers sit under `shared/` and are imported by the bot on startup.
- The command tree is configured in `app.py` when the bot boots.

## Linting & formatting
The project does not enforce a specific linter yet. Follow standard Black/ruff
conventions if you contribute new Python code.
