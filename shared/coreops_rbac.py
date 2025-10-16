"""Role helpers for CoreOps gating (Phase 2).

These mirror the legacy bots' behavior: role-based gating is done via role IDs
from the environment instead of user IDs. The helpers here intentionally ignore
non-numeric tokens so we can safely reuse old .env files without causing hard
crashes if a value is malformed.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Set, Tuple, Union

import discord
from discord.ext import commands

from shared.config import (
    get_admin_role_ids as _config_admin_roles,
    get_lead_role_ids as _config_lead_roles,
    get_recruiter_role_ids as _config_recruiter_roles,
    get_staff_role_ids as _config_staff_roles,
)

Memberish = Union[discord.abc.User, discord.Member]
ContextOrMember = Union[commands.Context, Memberish]

_DENIAL_LOG_THROTTLE_SEC = 30.0
_denial_log_cache: Dict[Tuple[Optional[int], str, Optional[int]], float] = {}

logger = logging.getLogger(__name__)


def _member_role_ids(member: Memberish | None) -> Set[int]:
    if not isinstance(member, discord.Member):
        return set()
    role_ids: Set[int] = set()
    for role in getattr(member, "roles", []) or []:
        role_id = getattr(role, "id", None)
        if role_id is None:
            continue
        try:
            role_ids.add(int(role_id))
        except (TypeError, ValueError):
            continue
    return role_ids


def _resolve_member(target: ContextOrMember | None) -> Memberish | None:
    if isinstance(target, commands.Context):
        return getattr(target, "author", None)
    return target if isinstance(target, (discord.Member, discord.abc.User)) else None


def get_admin_role_ids() -> Set[int]:
    return set(_config_admin_roles())


def get_staff_role_ids() -> Set[int]:
    return set(_config_staff_roles())


def get_recruiter_role_ids() -> Set[int]:
    return set(_config_recruiter_roles())


def get_lead_role_ids() -> Set[int]:
    return set(_config_lead_roles())


def is_staff_member(target: ContextOrMember | None) -> bool:
    member = _resolve_member(target)
    if member is None:
        return False
    member_roles = _member_role_ids(member)
    if not member_roles:
        return False
    admin_roles = get_admin_role_ids()
    if admin_roles and admin_roles.intersection(member_roles):
        return True
    staff_roles = get_staff_role_ids()
    return bool(staff_roles.intersection(member_roles))


def is_admin_member(target: ContextOrMember | None) -> bool:
    member = _resolve_member(target)
    if member is None:
        return False
    admin_roles = get_admin_role_ids()
    if not admin_roles:
        return False
    return bool(admin_roles.intersection(_member_role_ids(member)))


def is_recruiter(target: ContextOrMember | None) -> bool:
    member = _resolve_member(target)
    if member is None:
        return False
    roles = _member_role_ids(member)
    if not roles:
        return False
    admin_roles = get_admin_role_ids()
    if admin_roles and admin_roles.intersection(roles):
        return True
    recruiter_roles = get_recruiter_role_ids()
    return bool(recruiter_roles.intersection(roles))


def is_lead(target: ContextOrMember | None) -> bool:
    member = _resolve_member(target)
    if member is None:
        return False
    roles = _member_role_ids(member)
    if not roles:
        return False
    admin_roles = get_admin_role_ids()
    if admin_roles and admin_roles.intersection(roles):
        return True
    lead_roles = get_lead_role_ids()
    return bool(lead_roles.intersection(roles))


def can_manage_guild(member: discord.Member | None) -> bool:
    if not isinstance(member, discord.Member):
        return False
    perms = getattr(member, "guild_permissions", None)
    if perms is None:
        return False
    if getattr(perms, "administrator", False):
        return True
    return bool(getattr(perms, "manage_guild", False))


def ops_gate(member: discord.Member | None) -> bool:
    if member is None:
        return False
    if is_admin_member(member) or is_staff_member(member):
        return True
    return can_manage_guild(member)


async def _reply(ctx: commands.Context, message: str) -> None:
    try:
        await ctx.reply(message, mention_author=False)
    except Exception:
        pass


async def _send_guild_only_denial(ctx: commands.Context) -> None:
    await _reply(ctx, "This command can only be used in servers.")


async def _send_staff_denial(ctx: commands.Context) -> None:
    await _reply(ctx, "Staff only.")


async def _send_admin_denial(ctx: commands.Context) -> None:
    await _reply(ctx, "Admins only.")


def _log_staff_denial(ctx: commands.Context) -> None:
    author = getattr(ctx, "author", None)
    user_id = getattr(author, "id", None)
    command = getattr(getattr(ctx, "command", None), "qualified_name", None) or "unknown"
    guild = getattr(getattr(ctx, "guild", None), "id", None)
    key = (
        int(user_id) if isinstance(user_id, int) else None,
        command,
        int(guild) if isinstance(guild, int) else None,
    )
    now = time.monotonic()
    last = _denial_log_cache.get(key)
    if last is not None and now - last < _DENIAL_LOG_THROTTLE_SEC:
        return
    _denial_log_cache[key] = now
    logger.info(
        "Denied ops command '%s' for user %s in guild %s",
        command,
        user_id if user_id is not None else "unknown",
        guild if guild is not None else "DM",
    )


def _log_admin_denial(ctx: commands.Context) -> None:
    author = getattr(ctx, "author", None)
    user_id = getattr(author, "id", None)
    command = getattr(getattr(ctx, "command", None), "qualified_name", None) or "unknown"
    guild = getattr(getattr(ctx, "guild", None), "id", None)
    key = (
        int(user_id) if isinstance(user_id, int) else None,
        command,
        int(guild) if isinstance(guild, int) else None,
    )
    now = time.monotonic()
    last = _denial_log_cache.get(key)
    if last is not None and now - last < _DENIAL_LOG_THROTTLE_SEC:
        return
    _denial_log_cache[key] = now
    logger.info(
        "Denied admin command '%s' for user %s in guild %s",
        command,
        user_id if user_id is not None else "unknown",
        guild if guild is not None else "DM",
    )


def _log_admin_role_config_missing(ctx: commands.Context) -> None:
    command = getattr(getattr(ctx, "command", None), "qualified_name", None) or "unknown"
    guild = getattr(getattr(ctx, "guild", None), "id", None)
    logger.error(
        "No admin roles configured; falling back to Administrator permission for command '%s' in guild %s",
        command,
        guild if guild is not None else "DM",
    )


def ops_only() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if getattr(ctx, "guild", None) is None:
            await _send_guild_only_denial(ctx)
            raise commands.CheckFailure("Guild only.")
        member = getattr(ctx, "author", None)
        if isinstance(member, discord.Member) and ops_gate(member):
            return True
        await _send_staff_denial(ctx)
        _log_staff_denial(ctx)
        raise commands.CheckFailure("Staff only.")

    return commands.check(predicate)


def admin_only() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if getattr(ctx, "guild", None) is None:
            await _send_guild_only_denial(ctx)
            raise commands.CheckFailure("Guild only.")

        member = getattr(ctx, "author", None)
        if isinstance(member, discord.Member):
            admin_roles = get_admin_role_ids()
            member_roles = _member_role_ids(member)
            if admin_roles:
                if admin_roles.intersection(member_roles):
                    return True
            else:
                _log_admin_role_config_missing(ctx)
                perms = getattr(member, "guild_permissions", None)
                if getattr(perms, "administrator", False):
                    return True

        await _send_admin_denial(ctx)
        _log_admin_denial(ctx)
        raise commands.CheckFailure("Admins only.")

    return commands.check(predicate)


def guild_only_denied_msg() -> commands.Check[Any]:
    async def predicate(ctx: commands.Context) -> bool:
        if getattr(ctx, "guild", None) is None:
            await _send_guild_only_denial(ctx)
            raise commands.CheckFailure("Guild only.")
        return True

    return commands.check(predicate)
