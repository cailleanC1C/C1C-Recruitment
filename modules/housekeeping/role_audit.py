from __future__ import annotations

"""Scheduled audit for roles and visitor ticket hygiene."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord
from discord.ext import commands

from modules.common.tickets import TicketThread, fetch_ticket_threads
from shared.config import (
    get_admin_audit_dest_id,
    get_allowed_guild_ids,
    get_clan_role_ids,
    get_promo_channel_id,
    get_raid_role_id,
    get_visitor_role_id,
    get_wandering_souls_role_id,
    get_welcome_channel_id,
)

log = logging.getLogger("c1c.housekeeping.role_audit")

ROLE_AUDIT_REASON = "Housekeeping role audit"


@dataclass(slots=True)
class AuditResult:
    checked: int = 0
    auto_fixed_strays: list[discord.Member] | None = None
    auto_fixed_wanderers: list[discord.Member] | None = None
    wanderers_with_clans: list[tuple[discord.Member, list[discord.Role]]] | None = None
    visitors_no_ticket: list[discord.Member] | None = None
    visitors_closed_only: list[tuple[discord.Member, list[TicketThread]]] | None = None
    visitors_extra_roles: list[tuple[discord.Member, list[discord.Role], list[TicketThread]]] | None = None


def _member_roles(member: discord.Member) -> set[int]:
    return {getattr(role, "id", 0) for role in getattr(member, "roles", [])}


def _classify_roles(
    member_roles: set[int], *, raid_role_id: int, wanderer_role_id: int, clan_role_ids: set[int]
) -> str:
    has_raid = raid_role_id in member_roles
    has_wanderer = wanderer_role_id in member_roles
    has_clan = bool(member_roles & clan_role_ids)

    if has_raid and not has_clan and not has_wanderer:
        return "stray"
    if has_raid and has_wanderer and not has_clan:
        return "drop_raid"
    if has_wanderer and has_clan:
        return "wander_with_clan"
    return "ok"


def _extra_roles(member: discord.Member, visitor_role_id: int) -> list[discord.Role]:
    visitor_and_everyone = {visitor_role_id, getattr(getattr(member, "guild", None), "id", -1)}
    extras: list[discord.Role] = []
    for role in getattr(member, "roles", []):
        if getattr(role, "id", 0) in visitor_and_everyone:
            continue
        extras.append(role)
    return extras


def _format_member(member: discord.Member) -> str:
    mention = getattr(member, "mention", None)
    if mention:
        return mention
    name = getattr(member, "display_name", None) or getattr(member, "name", None)
    if name:
        return f"{name} ({getattr(member, 'id', 'unknown')})"
    return str(getattr(member, "id", "unknown"))


def _format_roles(roles: Iterable[discord.Role]) -> str:
    labels = []
    for role in roles:
        name = getattr(role, "name", "")
        labels.append(f"`{name}`" if name else f"`{getattr(role, 'id', 'role')}`")
    return ", ".join(labels) if labels else "`-`"


def _format_ticket_links(tickets: Sequence[TicketThread]) -> str:
    return ", ".join(f"[{ticket.name}]({ticket.url})" for ticket in tickets) or "-"


async def _apply_role_changes(
    member: discord.Member,
    *,
    remove: Sequence[discord.Role] = (),
    add: Sequence[discord.Role] = (),
) -> bool:
    try:
        if remove:
            await member.remove_roles(*remove, reason=ROLE_AUDIT_REASON)
        if add:
            await member.add_roles(*add, reason=ROLE_AUDIT_REASON)
    except discord.Forbidden:
        log.warning(
            "role audit skipped member — missing permissions",
            extra={"member_id": getattr(member, "id", None)},
        )
        return False
    except discord.HTTPException as exc:
        log.warning(
            "role audit member update failed",
            exc_info=True,
            extra={"member_id": getattr(member, "id", None), "error": str(exc)},
        )
        return False
    return True


async def _audit_guild(
    bot: commands.Bot,
    guild: discord.Guild,
    *,
    raid_role_id: int,
    wanderer_role_id: int,
    visitor_role_id: int,
    clan_role_ids: set[int],
    raid_role_name: str,
    wanderer_role_name: str,
) -> AuditResult | None:
    raid_role = guild.get_role(raid_role_id)
    wanderer_role = guild.get_role(wanderer_role_id)
    visitor_role = guild.get_role(visitor_role_id)
    if not all((raid_role, wanderer_role, visitor_role)):
        log.warning(
            "role audit skipped guild — missing roles",
            extra={
                "guild_id": getattr(guild, "id", None),
                "raid": bool(raid_role),
                "wanderer": bool(wanderer_role),
                "visitor": bool(visitor_role),
            },
        )
        return None

    try:
        members = [member async for member in guild.fetch_members(limit=None)]
    except Exception:
        members = list(getattr(guild, "members", []))

    tickets = await fetch_ticket_threads(
        bot,
        include_archived=True,
        with_members=True,
        guild_id=getattr(guild, "id", None),
    )

    ticket_map: dict[int, list[TicketThread]] = {}
    for ticket in tickets:
        for member_id in ticket.member_ids:
            ticket_map.setdefault(int(member_id), []).append(ticket)

    clan_lookup = {role.id: role for role in getattr(guild, "roles", []) if role.id in clan_role_ids}

    result = AuditResult(
        checked=len(members),
        auto_fixed_strays=[],
        auto_fixed_wanderers=[],
        wanderers_with_clans=[],
        visitors_no_ticket=[],
        visitors_closed_only=[],
        visitors_extra_roles=[],
    )

    for member in members:
        member_roles = _member_roles(member)

        classification = _classify_roles(
            member_roles,
            raid_role_id=raid_role_id,
            wanderer_role_id=wanderer_role_id,
            clan_role_ids=clan_role_ids,
        )
        if classification == "stray":
            changed = await _apply_role_changes(
                member, remove=(raid_role,), add=(wanderer_role,)
            )
            if changed:
                result.auto_fixed_strays.append(member)
            continue

        if classification == "drop_raid":
            changed = await _apply_role_changes(member, remove=(raid_role,))
            if changed:
                result.auto_fixed_wanderers.append(member)
            continue

        if classification == "wander_with_clan":
            clan_roles = [clan_lookup[role_id] for role_id in member_roles & clan_role_ids if role_id in clan_lookup]
            result.wanderers_with_clans.append((member, clan_roles))

        if visitor_role_id not in member_roles:
            continue

        member_tickets = ticket_map.get(getattr(member, "id", 0), [])
        open_tickets = [ticket for ticket in member_tickets if ticket.is_open]

        extras = _extra_roles(member, visitor_role_id)
        if extras:
            result.visitors_extra_roles.append((member, extras, member_tickets))

        if not member_tickets:
            result.visitors_no_ticket.append(member)
            continue

        if not open_tickets:
            result.visitors_closed_only.append((member, member_tickets))

    return result


def _render_section(title: str, lines: Sequence[str]) -> list[str]:
    if not lines:
        return [title, "• None"]
    return [title, *lines]


def _render_report(
    *,
    summary: AuditResult,
    raid_role_name: str,
    wanderer_role_name: str,
) -> str:
    date_text = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parts: list[str] = [
        "🧹 Role & Visitor Audit",
        f"Date: {date_text}",
        f"Checked: {summary.checked} members",
        "",
    ]

    stray_lines = [
        f"• {_format_member(member)} – Removed `{raid_role_name}`, added `{wanderer_role_name}` (no clan tags)"
        for member in (summary.auto_fixed_strays or [])
    ]
    wanderer_lines = [
        f"• {_format_member(member)} – Removed `{raid_role_name}`, kept `{wanderer_role_name}` (no clan tags)"
        for member in (summary.auto_fixed_wanderers or [])
    ]
    parts.extend(_render_section("1) Auto-fixed stray members", stray_lines + wanderer_lines))
    parts.append("")

    manual_lines = [
        f"• {_format_member(member)} – Has `{wanderer_role_name}` and clan tags: {_format_roles(clan_roles)}"
        for member, clan_roles in (summary.wanderers_with_clans or [])
    ]
    parts.extend(
        _render_section(
            "2) Manual review – Wandering Souls with clan tags",
            manual_lines,
        )
    )
    parts.append("")

    visitor_no_ticket = [f"• {_format_member(member)} – no ticket found" for member in (summary.visitors_no_ticket or [])]
    parts.extend(_render_section("3) Visitors without any ticket", visitor_no_ticket))
    parts.append("")

    visitor_closed_only = [
        f"• {_format_member(member)} – Tickets: {_format_ticket_links(tickets)}"
        for member, tickets in (summary.visitors_closed_only or [])
    ]
    parts.extend(_render_section("4) Visitors with only closed tickets", visitor_closed_only))
    parts.append("")

    visitor_extra_roles = [
        f"• {_format_member(member)} – Roles: {_format_roles(roles)} – Tickets: {_format_ticket_links(tickets)}"
        for member, roles, tickets in (summary.visitors_extra_roles or [])
    ]
    parts.extend(_render_section("5) Visitors with extra roles", visitor_extra_roles))

    return "\n".join(parts).strip()


async def run_role_and_visitor_audit(bot: commands.Bot) -> tuple[bool, str]:
    raid_role_id = get_raid_role_id()
    wanderer_role_id = get_wandering_souls_role_id()
    visitor_role_id = get_visitor_role_id()
    clan_role_ids = get_clan_role_ids()
    dest_id = get_admin_audit_dest_id()

    if not all((raid_role_id, wanderer_role_id, visitor_role_id, clan_role_ids, dest_id)):
        return False, "config-missing"

    if not (get_welcome_channel_id() or get_promo_channel_id()):
        return False, "ticket-channels-missing"

    allowed = get_allowed_guild_ids()
    target_guilds = [guild for guild in bot.guilds if not allowed or guild.id in allowed]
    if not target_guilds:
        return False, "no-guilds"

    raid_role_name = "Raid"
    wanderer_role_name = "Wandering Souls"
    aggregated = AuditResult(
        checked=0,
        auto_fixed_strays=[],
        auto_fixed_wanderers=[],
        wanderers_with_clans=[],
        visitors_no_ticket=[],
        visitors_closed_only=[],
        visitors_extra_roles=[],
    )

    for guild in target_guilds:
        raid_role = guild.get_role(raid_role_id)
        wanderer_role = guild.get_role(wanderer_role_id)
        if raid_role and getattr(raid_role, "name", None):
            raid_role_name = raid_role.name
        if wanderer_role and getattr(wanderer_role, "name", None):
            wanderer_role_name = wanderer_role.name

        result = await _audit_guild(
            bot,
            guild,
            raid_role_id=raid_role_id,
            wanderer_role_id=wanderer_role_id,
            visitor_role_id=visitor_role_id,
            clan_role_ids=clan_role_ids,
            raid_role_name=raid_role_name,
            wanderer_role_name=wanderer_role_name,
        )
        if result is None:
            continue

        aggregated.checked += result.checked
        aggregated.auto_fixed_strays.extend(result.auto_fixed_strays or [])
        aggregated.auto_fixed_wanderers.extend(result.auto_fixed_wanderers or [])
        aggregated.wanderers_with_clans.extend(result.wanderers_with_clans or [])
        aggregated.visitors_no_ticket.extend(result.visitors_no_ticket or [])
        aggregated.visitors_closed_only.extend(result.visitors_closed_only or [])
        aggregated.visitors_extra_roles.extend(result.visitors_extra_roles or [])

    if aggregated.checked == 0:
        return False, "no-members"

    await bot.wait_until_ready()
    channel = bot.get_channel(dest_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(dest_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            log.warning("role audit destination lookup failed", exc_info=True)
            return False, f"dest:{type(exc).__name__}"

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "dest-invalid"

    message = _render_report(
        summary=aggregated,
        raid_role_name=raid_role_name,
        wanderer_role_name=wanderer_role_name,
    )

    try:
        await channel.send(content=message)
    except Exception as exc:
        log.warning("failed to send role audit report", exc_info=True)
        return False, f"send:{type(exc).__name__}"

    return True, "-"


__all__ = ["run_role_and_visitor_audit"]
