"""Role helpers backed by the shared configuration loader."""
from __future__ import annotations

from typing import Optional, Set

import discord

from shared.config import get_shared_config


def get_admin_role_id() -> Optional[int]:
    """Return the single admin role id, or None if unset."""
    return get_shared_config().admin_role_id


def get_staff_role_ids() -> Set[int]:
    """Return the (possibly empty) set of staff role ids."""
    return set(get_shared_config().staff_role_ids)


def _member_role_ids(member: discord.abc.User | discord.Member) -> Set[int]:
    if not isinstance(member, discord.Member):
        return set()
    role_ids: Set[int] = set()
    for role in getattr(member, "roles", []) or []:
        role_id = getattr(role, "id", None)
        if role_id is not None:
            try:
                role_ids.add(int(role_id))
            except (TypeError, ValueError):
                continue
    return role_ids


def is_staff_member(member: discord.abc.User | discord.Member) -> bool:
    member_roles = _member_role_ids(member)
    if not member_roles:
        return False
    admin_role_id = get_admin_role_id()
    if admin_role_id is not None and admin_role_id in member_roles:
        return True
    staff_ids = get_staff_role_ids()
    return bool(staff_ids.intersection(member_roles))


def is_admin_member(member: discord.abc.User | discord.Member) -> bool:
    admin_role_id = get_admin_role_id()
    if admin_role_id is None:
        return False
    return admin_role_id in _member_role_ids(member)
