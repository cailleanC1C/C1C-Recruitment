"""Cluster role map builder backed by the WhoWeAre worksheet."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence

import discord

from shared.config import get_recruitment_sheet_id
from shared.sheets import recruitment
from shared.sheets.async_core import afetch_records

log = logging.getLogger("c1c.cluster_role_map")

CATEGORY_EMOJIS: Dict[str, str] = {
    "clusterleadership": "🔥",
    "clustersupport": "🛡️",
    "recruitment": "🌱",
    "communitysupport": "📘",
    "specialsupporters": "💎",
}

DEFAULT_DESCRIPTION = "no description set"


@dataclass(slots=True)
class RoleMapRow:
    """Structured view of a WhoWeAre worksheet row."""

    category: str
    role_id: int
    sheet_role_name: str
    role_description: str


@dataclass(slots=True)
class RoleMapRender:
    """Rendered output plus summary counts for logging."""

    message: str
    category_count: int
    role_count: int
    unassigned_roles: int


class RoleMapLoadError(RuntimeError):
    """Raised when the WhoWeAre worksheet cannot be read."""


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _cell(row: Mapping[str, object], *names: str) -> str:
    wanted = {name.strip().lower() for name in names if name}
    for column, value in row.items():
        column_name = str(column or "").strip().lower()
        if column_name in wanted:
            return _normalize_text(value)
    return ""


def parse_role_map_records(rows: Sequence[Mapping[str, object]]) -> List[RoleMapRow]:
    entries: List[RoleMapRow] = []
    for row in rows:
        category = _cell(row, "category")
        if not category:
            continue
        role_id_text = _cell(row, "role_id", "role id")
        if not role_id_text:
            continue
        try:
            role_id = int(role_id_text)
        except (TypeError, ValueError):
            continue
        sheet_role_name = _cell(row, "role_name", "role name")
        role_description = _cell(row, "role_description", "role description")
        entries.append(
            RoleMapRow(
                category=category,
                role_id=role_id,
                sheet_role_name=sheet_role_name,
                role_description=role_description,
            )
        )
    return entries


async def fetch_role_map_rows(tab_name: str | None = None) -> List[RoleMapRow]:
    """Return parsed WhoWeAre rows from the configured worksheet."""

    sheet_id = _normalize_text(get_recruitment_sheet_id())
    if not sheet_id:
        raise RoleMapLoadError("Recruitment sheet ID is missing")

    rolemap_tab = _normalize_text(tab_name) or recruitment.get_role_map_tab_name()
    if not rolemap_tab:
        raise RoleMapLoadError("Role map tab name missing")

    try:
        records = await afetch_records(sheet_id, rolemap_tab)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - network/runtime failure
        log.warning("cluster_role_map: failed to read worksheet", exc_info=True)
        raise RoleMapLoadError(f"Failed to load worksheet '{rolemap_tab}': {exc}") from exc

    return parse_role_map_records(records)


def _category_order(entries: Iterable[RoleMapRow]) -> tuple[List[str], Dict[str, List[RoleMapRow]]]:
    order: List[str] = []
    grouped: Dict[str, List[RoleMapRow]] = {}
    for entry in entries:
        if entry.category not in grouped:
            grouped[entry.category] = []
            order.append(entry.category)
        grouped[entry.category].append(entry)
    return order, grouped


def _category_emoji(name: str) -> str:
    normalized = name.strip().lower()
    return CATEGORY_EMOJIS.get(normalized, "•")


def build_role_map_render(guild: discord.Guild | object, entries: Sequence[RoleMapRow]) -> RoleMapRender:
    """Compose the Discord message for the supplied WhoWeAre rows."""

    order, grouped = _category_order(entries)
    lines = [
        "💙 WHO WE ARE — C1C Role Map",
        "Roles first. Humans optional. Snark mandatory.",
        "",
    ]

    role_count = 0
    unassigned_roles = 0

    get_role = getattr(guild, "get_role", None)

    for category in order:
        emoji = _category_emoji(category)
        lines.append(f"{emoji} {category}")
        lines.append("")
        for row in grouped.get(category, []):
            role_count += 1
            role = get_role(row.role_id) if callable(get_role) else None
            display_name = ""
            if role is not None:
                display_name = _normalize_text(getattr(role, "name", ""))
                members = list(getattr(role, "members", []) or [])
            else:
                members = []
            if not display_name:
                display_name = row.sheet_role_name or f"role {row.role_id}"
            description = row.role_description or DEFAULT_DESCRIPTION
            lines.append(f"**{display_name}** — {description}")
            if members:
                mentions = ", ".join(str(getattr(member, "mention", getattr(member, "name", ""))) for member in members)
                lines.append(f"• {mentions}")
            else:
                lines.append("• (currently unassigned)")
                unassigned_roles += 1
            lines.append("")

    if not order:
        lines.append("(No role entries found.)")

    message = "\n".join(lines).rstrip()
    return RoleMapRender(
        message=message,
        category_count=len(order),
        role_count=role_count,
        unassigned_roles=unassigned_roles,
    )


__all__ = [
    "CATEGORY_EMOJIS",
    "RoleMapRow",
    "RoleMapRender",
    "RoleMapLoadError",
    "build_role_map_render",
    "fetch_role_map_rows",
    "parse_role_map_records",
]

