"""Loaders for legacy Matchmaker features."""

from __future__ import annotations

import importlib
from typing import Optional

from discord.ext import commands

_LEGACY_MODULE = "AUDIT.20251010_src.MM.bot_clanmatch_prefix"

_loaded_module: Optional[object] = None


async def ensure_loaded(bot: commands.Bot) -> object:
    """Idempotently import the legacy module and graft its commands onto *bot*."""
    global _loaded_module
    if _loaded_module is not None:
        return _loaded_module

    try:
        legacy = importlib.import_module(_LEGACY_MODULE)
    except ModuleNotFoundError as exc:  # pragma: no cover - surfaced at runtime
        raise RuntimeError(
            "Legacy Matchmaker module not available. Ensure audit sources are vendored."
        ) from exc
    legacy_bot = getattr(legacy, "bot")

    commands_to_add = list(getattr(legacy_bot, "commands", []))
    listeners = {
        name: tuple(funcs)
        for name, funcs in getattr(legacy_bot, "extra_events", {}).items()
    }
    checks = tuple(getattr(legacy_bot, "checks", ()))
    before = getattr(legacy_bot, "_before_invoke", None)
    after = getattr(legacy_bot, "_after_invoke", None)
    check_once = getattr(legacy_bot, "_check_once", None)

    legacy.bot = bot  # make module-level lookups resolve to the shared bot

    try:
        bot.remove_command("help")
    except Exception:
        pass

    for check in checks:
        bot.add_check(check)
    if before:
        bot.before_invoke(before)
    if after:
        bot.after_invoke(after)
    if check_once:
        bot.check_once(check_once)

    for command in commands_to_add:
        if bot.get_command(command.name):
            bot.remove_command(command.name)
        bot.add_command(command)

    for name, funcs in listeners.items():
        for func in funcs:
            bot.add_listener(func, name)

    _loaded_module = legacy
    return legacy
