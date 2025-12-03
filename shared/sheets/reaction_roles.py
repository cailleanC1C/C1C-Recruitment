"""Reaction role configuration loader from Sheets."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, NamedTuple

from shared.config import cfg, get_milestones_sheet_id
from shared.sheets.async_core import afetch_records

log = logging.getLogger("c1c.sheets.reaction_roles")

_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))


def _tab_name() -> str:
    tab = cfg.get("REACTION_ROLES_TAB")
    if isinstance(tab, str) and tab.strip():
        return tab.strip()
    env_tab = os.getenv("REACTION_ROLES_TAB")
    if isinstance(env_tab, str) and env_tab.strip():
        return env_tab.strip()
    return "ReactionRoles"


class ReactionRoleRow(NamedTuple):
    key: str
    emoji_raw: str
    role_id: int
    channel_id: int | None
    thread_id: int | None
    active: bool


@dataclass(frozen=True, slots=True)
class _ParseContext:
    sheet_tail: str
    tab: str


def _sheet_id() -> str:
    sheet_id = get_milestones_sheet_id().strip()
    if not sheet_id:
        raise RuntimeError("MILESTONES_SHEET_ID not set")
    return sheet_id


def _sheet_tail(sheet_id: str) -> str:
    return sheet_id[-6:] if len(sheet_id) >= 6 else sheet_id


def _parse_bool(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalise_key(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_row(row: dict[str, object], ctx: _ParseContext) -> ReactionRoleRow | None:
    key = _normalise_key(row.get("KEY") or row.get("key"))
    emoji_raw = (row.get("EMOJI") or row.get("emoji") or "").strip()
    role_id_raw = row.get("ROLE_ID") or row.get("role_id")

    if not key or not emoji_raw or role_id_raw in (None, ""):
        return None

    role_id = _parse_int(role_id_raw)
    channel_id = _parse_int(row.get("CHANNEL_ID") or row.get("channel_id"))
    thread_id = _parse_int(row.get("THREAD_ID") or row.get("thread_id"))
    active = _parse_bool(row.get("ACTIVE") or row.get("active"))

    if role_id is None:
        log.warning(
            "reaction role row skipped: invalid role_id",
            extra={
                "sheet": ctx.sheet_tail,
                "tab": ctx.tab,
                "key": key,
                "emoji": emoji_raw,
            },
        )
        return None

    return ReactionRoleRow(
        key=key,
        emoji_raw=emoji_raw,
        role_id=role_id,
        channel_id=channel_id,
        thread_id=thread_id,
        active=active,
    )


def _parse_rows(records: Iterable[dict[str, object]], ctx: _ParseContext) -> tuple[ReactionRoleRow, ...]:
    parsed: list[ReactionRoleRow] = []
    for raw in records:
        row = _parse_row(raw, ctx)
        if row is None:
            continue
        parsed.append(row)
    return tuple(parsed)


async def fetch_reaction_role_rows_async() -> tuple[ReactionRoleRow, ...]:
    sheet_id = _sheet_id()
    tab = _tab_name()
    sheet_tail = _sheet_tail(sheet_id)
    sheet_display = (
        f"milestones:…{sheet_tail}" if len(sheet_id) > len(sheet_tail) else f"milestones:{sheet_tail}"
    )
    log.info(
        "📦 Cache = bucket=reaction_roles • sheet=%s • tab=%s • source=resolved",
        sheet_display,
        tab,
        extra={"sheet_tail": sheet_tail, "tab": tab},
    )
    records = await afetch_records(sheet_id, tab)
    return _parse_rows(records or [], _ParseContext(sheet_tail=sheet_tail, tab=tab))


async def _load_reaction_roles() -> tuple[ReactionRoleRow, ...]:
    return await fetch_reaction_role_rows_async()


def register_cache_buckets() -> None:
    from shared.sheets.cache_service import cache

    if cache.get_bucket("reaction_roles") is not None:
        return
    cache.register("reaction_roles", _CACHE_TTL, _load_reaction_roles)


def cached_reaction_roles() -> tuple[ReactionRoleRow, ...] | None:
    from shared.sheets.cache_service import cache

    bucket = cache.get_bucket("reaction_roles")
    if bucket is None:
        return None
    value = bucket.value
    if value is None:
        return None
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return None


__all__ = [
    "ReactionRoleRow",
    "cached_reaction_roles",
    "fetch_reaction_role_rows_async",
    "register_cache_buckets",
]
