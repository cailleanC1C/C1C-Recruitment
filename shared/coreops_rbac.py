"""Role helpers for CoreOps gating (Phase 1).

These mirror the legacy bots' behavior: staff/admin gating is done via role IDs
from the environment instead of user IDs. The helpers here intentionally ignore
non-numeric tokens so we can safely reuse old .env files without causing hard
crashes if a value is malformed.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Iterable, Optional, Set

import discord

_ROLE_SPLIT_RE = re.compile(r"[,\s]+")


def _parse_role_tokens(raw: str) -> Iterable[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    return (tok for tok in _ROLE_SPLIT_RE.split(raw) if tok)


def _safe_int(tok: str) -> Optional[int]:
    if not tok:
        return None
    match = re.search(r"\d+", tok)
    if not match:
        return None
    try:
        return int(match.group(0))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_admin_role_id() -> Optional[int]:
    """Return the single admin role id, or None if unset/invalid."""
    for tok in _parse_role_tokens(os.getenv("ADMIN_ROLE_ID", "")):
        value = _safe_int(tok)
        if value is not None:
            return value
    return None


@lru_cache(maxsize=1)
def get_staff_role_ids() -> Set[int]:
    """Return the (possibly empty) set of staff role ids."""
    ids: Set[int] = set()
    for tok in _parse_role_tokens(os.getenv("STAFF_ROLE_IDS", "")):
        value = _safe_int(tok)
        if value is not None:
            ids.add(value)
    return ids


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
