### Entrypoint
- `bot_welcomecrew.py` instantiates a prefix bot with `!`, but the module never registers a `clan` command (only admin/maintenance handlers such as `!help`, `!env_check`, etc.).

- Because no handler exists, any `!clan` invocation falls through to the global `on_command_error`, which silently returns on `CommandNotFound`, leaving the user with no output.

- The module loads as a standalone script via `asyncio.run(_boot())`, so this behavior applies wherever the script is deployed.



### Routing
- With no command implementation, the bot never posts a response—`on_command_error` exits early and `on_message` merely delegates to `bot.process_commands`, which finds nothing to execute.



### UI
- There is no reaction or button UI tied to `!clan`; the only interactive view in the module is the thread tag picker used by close-detection flows, not by any command.



### Embeds & Data
- No clan profile or entry embed builder exists—the command list and helper functions only cover admin utilities and sheet/tag caches, with no code to assemble a clan view.

- Clan tag data is loaded solely for watcher logic (`_load_clan_tags`) and never tied to a prefix lookup from a `<tag>` argument.



### Emoji/Crest
- There is no crest/thumbnail generation path; the sole UI class manipulates plain-text content and never calls `set_thumbnail` or attaches files for clan output.



### Validation & Errors
- Since the command is undefined, there is no tag normalization or explicit error message—unknown-command handling absorbs the request without feedback.



### Toggles & Help
- No feature flag governs a clan command; the flag block covers other utilities only.


- Neither the in-bot help card nor the project README lists `!clan`, confirming it is not exposed to users.



- Boot logs only attempt to preload clan tags for watcher caching and raise no warnings about a command surface.



### Divergences from Prod (observed)
- Prefix `!clan` simply yields silence (unknown command), so none of the prod behaviors—channel reply, 💡 reaction flip, clan crest thumbnail, or entry criteria text—exist in this codebase.



