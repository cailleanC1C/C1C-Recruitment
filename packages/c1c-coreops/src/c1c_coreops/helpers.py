"""Utilities for tagging CoreOps commands with visibility tiers."""

from __future__ import annotations

from typing import Callable, Dict

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


def tier(level: str) -> Callable:
    """Decorator: attach a visibility tier ('user' | 'staff' | 'admin') to a command."""

    def wrapper(cmd):
        _set_tier(cmd, level)
        return cmd

    return wrapper


def rehydrate_tiers(bot) -> None:
    """
    Reapply tiers to commands after cogs/extensions load.
    Useful because Command.copy() can drop ad-hoc attributes.
    """

    for cmd in bot.walk_commands():
        # Prefer extras if already present
        level = None
        try:
            extras = getattr(cmd, "extras", None)
            if isinstance(extras, dict):
                level = extras.get("tier")
        except Exception:
            level = None

        if not level:
            # Fallback to registry by qualified_name, then name.
            qn = getattr(cmd, "qualified_name", None)
            if qn and qn in _TIER_REGISTRY:
                level = _TIER_REGISTRY[qn]
            elif getattr(cmd, "name", None) in _TIER_REGISTRY:
                level = _TIER_REGISTRY[getattr(cmd, "name")]

        if level:
            _set_tier(cmd, level)


def audit_tiers(bot, logger=None) -> None:
    missing: list[str] = []
    for cmd in bot.walk_commands():
        tier = None
        try:
            extras = getattr(cmd, "extras", None)
            if isinstance(extras, dict):
                tier = extras.get("tier")
        except Exception:
            pass
        tier = tier or getattr(cmd, "_tier", None)
        if not tier and cmd.qualified_name not in ("rec",):
            missing.append(cmd.qualified_name)
    if missing and logger is not None:
        logger.warning("Help tiers missing for: %s", ", ".join(sorted(missing)))
