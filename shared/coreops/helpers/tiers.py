"""Helpers for command tier tagging that survives discord.py command cloning."""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

# Qualified name -> tier (e.g., "rec help", "health")
_TIER_REGISTRY: Dict[str, str] = {}


def _set_tier(cmd, level: str) -> None:
    # Extras is stable across Command.copy() since discord.py 2.x.
    try:
        extras = getattr(cmd, "extras", None)
        if isinstance(extras, dict):
            extras["tier"] = level
    except Exception:
        pass

    # Also stamp an attribute for convenience on the current object.
    try:
        setattr(cmd, "_tier", level)
    except Exception:
        pass

    # Record in registry using the current qualified_name if available.
    qn = getattr(cmd, "qualified_name", None) or getattr(cmd, "name", None)
    if isinstance(qn, str):
        _TIER_REGISTRY[qn] = level


def _lookup_registry(cmd) -> Optional[str]:
    qn = getattr(cmd, "qualified_name", None)
    if isinstance(qn, str) and qn in _TIER_REGISTRY:
        return _TIER_REGISTRY[qn]

    name = getattr(cmd, "name", None)
    if isinstance(name, str) and name in _TIER_REGISTRY:
        return _TIER_REGISTRY[name]

    return None


def _resolve_tier(cmd) -> Optional[str]:
    try:
        extras = getattr(cmd, "extras", None)
        if isinstance(extras, dict):
            level = extras.get("tier")
            if isinstance(level, str) and level:
                return level
    except Exception:
        pass

    try:
        level_attr = getattr(cmd, "_tier", None)
    except Exception:
        level_attr = None
    if isinstance(level_attr, str) and level_attr:
        return level_attr

    return _lookup_registry(cmd)


def tier(level: str) -> Callable:
    """Decorator: attach a visibility tier ('user' | 'staff' | 'admin') to a command."""

    def wrapper(cmd):
        _set_tier(cmd, level)
        return cmd

    return wrapper


def rehydrate_tiers(bot) -> None:
    """Reapply tiers to commands after cogs/extensions load."""

    for cmd in bot.walk_commands():
        level = _resolve_tier(cmd)
        if level:
            _set_tier(cmd, level)


def audit_tiers(bot, log: "logging.Logger") -> None:
    """Emit a log entry when any command is missing a tier tag."""

    missing: list[str] = []
    seen: set[str] = set()

    for cmd in bot.walk_commands():
        identifier = getattr(cmd, "qualified_name", None) or getattr(cmd, "name", None)
        if not isinstance(identifier, str) or identifier in seen:
            continue
        seen.add(identifier)

        if identifier == "rec":
            # Group container does not represent an executable command.
            continue

        if not _resolve_tier(cmd):
            missing.append(identifier)

    if missing:
        log.warning("tier audit missing tags", extra={"missing": sorted(missing)})
    else:
        log.info("tier audit complete", extra={"commands": len(seen)})

