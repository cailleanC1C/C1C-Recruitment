"""Helpers for CoreOps refresh command RBAC."""

from __future__ import annotations

import datetime as dt
from typing import Any

from discord.ext import commands

from .coreops_rbac import is_admin_member, is_staff_member

UTC = dt.timezone.utc


def _admin_roles_configured() -> bool:
    """Return True when admin roles are configured (defaults to True)."""

    try:
        from .coreops_rbac import admin_roles_configured  # type: ignore
    except Exception:
        return True
    try:
        return bool(admin_roles_configured())  # type: ignore[misc]
    except Exception:
        return True


def _admin_check() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if not _admin_roles_configured():
            # Let the command body display the explicit disabled message.
            return True
        return is_admin_member(getattr(ctx, "author", None))

    return commands.check(predicate)


def _staff_check() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        author = getattr(ctx, "author", None)
        if is_staff_member(author) or is_admin_member(author):
            return True
        perms = getattr(getattr(author, "guild_permissions", None), "administrator", False)
        return bool(perms)

    return commands.check(predicate)


__all__ = [
    "UTC",
    "_admin_check",
    "_admin_roles_configured",
    "_staff_check",
]
