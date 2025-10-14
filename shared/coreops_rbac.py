"""Role helpers for CoreOps gating (Phase 2).

These mirror the legacy bots' behavior: role-based gating is done via role IDs
from the environment instead of user IDs. The helpers here intentionally ignore
non-numeric tokens so we can safely reuse old .env files without causing hard
crashes if a value is malformed.
"""
from __future__ import annotations

from typing import Set, Union

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
