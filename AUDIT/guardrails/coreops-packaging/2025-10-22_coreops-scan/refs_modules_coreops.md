# CoreOps Module Surface

## modules/coreops/__init__.py
- Public classes: _None_
- Public functions: _None_
- Public constants: _None_
- Cog classes: _None_
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

## modules/coreops/cog.py
- Public classes: _None_
- Public functions: setup (async)
- Public constants: _None_
- Cog classes: _None_
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

## modules/coreops/cron_summary.py
- Public classes: _None_
- Public functions: emit_daily_summary (async)
- Public constants: TAG
- Cog classes: _None_
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

## modules/coreops/cronlog.py
- Public classes: _None_
- Public functions: cron_task, read_metrics (async)
- Public constants: TAG
- Cog classes: _None_
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

## modules/coreops/helpers.py
- Public classes: _None_
- Public functions: audit_tiers, rehydrate_tiers, tier
- Public constants: _None_
- Cog classes: _None_
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

## modules/coreops/ops.py
- Public classes: Ops
- Public functions: setup (async)
- Public constants: _None_
- Cog classes: Ops (commands.Cog) defines no decorated command methods
- Import-time command registration: None detected (no bot.add_cog or command execution at module import)

### modules/coreops/ops.py details
- The `Ops` Cog subclass provides an extension stub for future status/admin commands; currently it exposes no command methods.
- `async def setup(bot)` adds the Cog when the extension is loaded; no side-effects occur unless the setup coroutine is awaited.
- Expected loading pathway: listed in `modules/common/runtime.py` extension loader via `await modules.coreops.ops.setup(bot)`; no automatic registration on import.

Doc last updated: 2025-10-22 (v0.9.5)
