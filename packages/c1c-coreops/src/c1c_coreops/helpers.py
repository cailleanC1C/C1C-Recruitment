"""Utilities for tagging CoreOps commands with visibility tiers."""

from __future__ import annotations

from typing import Callable, Dict, Sequence

from discord.ext import commands

# Qualified name -> tier (e.g., "ops help", "health")
_TIER_REGISTRY: Dict[str, str] = {}


def _ensure_extras(cmd) -> Dict[str, str]:
    try:
        extras = getattr(cmd, "extras", None)
    except Exception:
        extras = None
    if not isinstance(extras, dict):
        extras = {}
        try:
            setattr(cmd, "extras", extras)
        except Exception:
            pass
    return extras


def _install_command_metadata_accessors() -> None:
    if not hasattr(commands.Command, "function_group"):

        def _get_function_group(cmd):
            extras = getattr(cmd, "extras", None)
            if isinstance(extras, dict):
                return extras.get("function_group")
            return None

        def _set_function_group(cmd, value):
            extras = _ensure_extras(cmd)
            if value is None:
                extras.pop("function_group", None)
                return
            extras["function_group"] = value

        commands.Command.function_group = property(  # type: ignore[attr-defined]
            _get_function_group, _set_function_group
        )

    if not hasattr(commands.Command, "access_tier"):

        def _get_access_tier(cmd):
            extras = getattr(cmd, "extras", None)
            if isinstance(extras, dict):
                tier = extras.get("access_tier") or extras.get("tier")
                if tier is not None:
                    return tier
            return getattr(cmd, "_tier", None)

        def _set_access_tier(cmd, value):
            extras = _ensure_extras(cmd)
            if value is None:
                extras.pop("access_tier", None)
                return
            extras["access_tier"] = value

        commands.Command.access_tier = property(  # type: ignore[attr-defined]
            _get_access_tier, _set_access_tier
        )


_install_command_metadata_accessors()


def _set_tier(cmd, level: str) -> None:
    # Extras is stable across Command.copy() since discord.py 2.x.
    extras = _ensure_extras(cmd)
    extras["tier"] = level
    extras.setdefault("access_tier", level)
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
        extras = None
        try:
            extras = getattr(cmd, "extras", None)
        except Exception:
            extras = None
        if isinstance(extras, dict):
            level = extras.get("tier") or extras.get("access_tier")
        
        if not level:
            # Fallback to registry by qualified_name, then name.
            qn = getattr(cmd, "qualified_name", None)
            if qn and qn in _TIER_REGISTRY:
                level = _TIER_REGISTRY[qn]
            elif getattr(cmd, "name", None) in _TIER_REGISTRY:
                level = _TIER_REGISTRY[getattr(cmd, "name")]

        if level:
            _set_tier(cmd, level)


def help_metadata(
    *,
    function_group: str,
    section: str | None = None,
    access_tier: str | None = None,
    usage: str | None = None,
    flags: str | Sequence[str] | None = None,
) -> Callable:
    """Decorator to attach help layout metadata to a command."""

    def wrapper(cmd):
        extras = _ensure_extras(cmd)
        extras.setdefault("function_group", function_group)
        try:
            setattr(cmd, "function_group", function_group)
        except Exception:
            pass
        if section is not None:
            extras.setdefault("help_section", section)
        if access_tier is not None:
            extras["access_tier"] = access_tier
            try:
                setattr(cmd, "access_tier", access_tier)
            except Exception:
                pass
        if usage is not None:
            extras["help_usage"] = usage
        if flags is not None:
            if isinstance(flags, str):
                extras["help_flags"] = [flags]
            else:
                extras["help_flags"] = list(flags)
        return cmd

    return wrapper


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
        if not tier and cmd.qualified_name not in ("ops",):
            missing.append(cmd.qualified_name)
    if missing and logger is not None:
        logger.warning("Help tiers missing for: %s", ", ".join(sorted(missing)))
