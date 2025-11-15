"""Reservation command for holding clan seats inside ticket threads."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Optional

import discord
from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import is_admin_member, is_recruiter
from modules.common import feature_flags
from modules.common.logs import log as human_log
from modules.recruitment import availability
from modules.onboarding.watcher_welcome import (
    parse_welcome_thread_name,
    rename_thread_to_reserved,
)
from shared.config import get_promo_channel_id, get_welcome_channel_id
from shared.sheets import recruitment, reservations

log = logging.getLogger(__name__)

PROMPT_TIMEOUT_SECONDS = 300
ACTIVE_STATUS = "active"


class ReservationFlowAbort(Exception):
    """Raised when the interactive flow ends without creating a reservation."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class ReservationDetails:
    """Normalized output from the interactive reservation flow."""

    ticket_user_id: Optional[int]
    ticket_display: str
    ticket_username: Optional[str]
    reserved_until: dt.date
    notes: str


class ReservationConversation:
    """Interactive prompt that collects reservation metadata from staff."""

    CANCEL_KEYWORDS: Iterable[str] = ("cancel",)

    def __init__(
        self,
        ctx: commands.Context,
        *,
        clan_label: str,
        manual_open: int,
        active_reservations: int,
        wait_for: Callable[..., Awaitable[discord.Message]],
    ) -> None:
        self.ctx = ctx
        self._clan_label = clan_label
        self._manual_open = manual_open
        self._active_reservations = active_reservations
        self._wait_for = wait_for
        self._author_id = getattr(ctx.author, "id", None)
        self._channel_id = getattr(ctx.channel, "id", None)

    async def run(self) -> ReservationDetails:
        """Execute the full conversation flow and return reservation details."""

        user_id, display, username = await self._prompt_user()
        reserved_until = await self._prompt_date()

        notes = ""
        if self._effective_available <= 0:
            notes = await self._prompt_reason()

        while True:
            action = await self._confirm(display, reserved_until, notes)
            if action == "yes":
                return ReservationDetails(
                    ticket_user_id=user_id,
                    ticket_display=display,
                    ticket_username=username,
                    reserved_until=reserved_until,
                    notes=notes,
                )
            if action == "user":
                user_id, display, username = await self._prompt_user(reprompt=True)
                continue
            if action == "date":
                reserved_until = await self._prompt_date(reprompt=True)
                continue

    @property
    def _effective_available(self) -> int:
        return max(self._manual_open - self._active_reservations, 0)

    async def _prompt_user(
        self, *, reprompt: bool = False
    ) -> tuple[Optional[int], str, Optional[str]]:
        prompt = (
            f"Who do you want to reserve a spot for in `{self._clan_label}`?\n"
            "You can @mention them or paste their Discord ID. Type `cancel` to abort."
        )
        if not reprompt:
            await self.ctx.send(prompt)
        else:
            await self.ctx.send(
                "Please @mention the recruit or paste their Discord ID. Type `cancel` to abort."
            )

        while True:
            message = await self._next_message()
            content = (message.content or "").strip()
            lowered = content.lower()
            if lowered in self.CANCEL_KEYWORDS:
                await self.ctx.send("Reservation cancelled. No changes made.")
                raise ReservationFlowAbort("cancelled")

            mention = next(iter(getattr(message, "mentions", []) or []), None)
            if mention is not None:
                display = getattr(mention, "mention", f"<@{getattr(mention, 'id', '???')}>")
                ticket_username = _display_name(mention)
                return getattr(mention, "id", None), display, ticket_username

            match = re.search(r"\d+", content)
            if match:
                try:
                    candidate_id = int(match.group(0))
                except ValueError:
                    candidate_id = None
                if candidate_id is not None:
                    member = _resolve_member(self.ctx.guild, candidate_id)
                    if member is not None:
                        mention_text = getattr(member, "mention", f"<@{candidate_id}>")
                        return candidate_id, mention_text, _display_name(member)
                    return candidate_id, f"<@{candidate_id}>", None

            await self.ctx.send(
                "I didn't catch that. Please @mention the recruit or paste their Discord ID (or type `cancel`)."
            )

    async def _prompt_date(self, *, reprompt: bool = False) -> dt.date:
        prompt = (
            "Until which date do you want to reserve the spot?"
            " Please use `YYYY-MM-DD` (no time). Type `cancel` to abort."
        )
        if not reprompt:
            await self.ctx.send(prompt)
        else:
            await self.ctx.send(
                "Please provide the reservation end date in `YYYY-MM-DD` (or type `cancel`)."
            )

        while True:
            message = await self._next_message()
            content = (message.content or "").strip()
            lowered = content.lower()
            if lowered in self.CANCEL_KEYWORDS:
                await self.ctx.send("Reservation cancelled. No changes made.")
                raise ReservationFlowAbort("cancelled")
            try:
                parsed = dt.date.fromisoformat(content)
            except ValueError:
                parsed = None
            today = dt.date.today()
            if parsed is None or parsed < today:
                await self.ctx.send(
                    "Please use `YYYY-MM-DD` and make sure the date is today or later."
                )
                continue
            return parsed

    async def _prompt_reason(self) -> str:
        prompt = (
            f"Heads up: `{self._clan_label}` currently has 0 effective open spots when existing"
            " reservations are included. You can still reserve a seat, but please add a short"
            " reason (or type `cancel` to abort)."
        )
        await self.ctx.send(prompt)

        while True:
            message = await self._next_message()
            content = (message.content or "").strip()
            if content.lower() in self.CANCEL_KEYWORDS:
                await self.ctx.send("Reservation cancelled. No changes made.")
                raise ReservationFlowAbort("cancelled")
            if content:
                return content
            await self.ctx.send("Please add a short reason (or type `cancel` to abort).")

    async def _confirm(
        self, display: str, reserved_until: dt.date, notes: str
    ) -> str:
        lines = [
            f"Reserve 1 spot in `{self._clan_label}` for {display} until `{reserved_until.isoformat()}`.",
        ]
        if notes:
            lines.append(f"Reason: {notes}")
        lines.append("Type `yes` to save, `no` to cancel, or `change` to edit the recruit/date.")
        await self.ctx.send("\n".join(lines))

        while True:
            message = await self._next_message()
            content = (message.content or "").strip().lower()
            if content in self.CANCEL_KEYWORDS or content in {"no", "n"}:
                await self.ctx.send("Reservation cancelled. No changes made.")
                raise ReservationFlowAbort("cancelled")
            if content in {"yes", "y"}:
                return "yes"
            if content in {"change", "c"}:
                await self.ctx.send("Type `user` to change the recruit or `date` to change the end date.")
                while True:
                    followup = await self._next_message()
                    follow_content = (followup.content or "").strip().lower()
                    if follow_content in self.CANCEL_KEYWORDS:
                        await self.ctx.send("Reservation cancelled. No changes made.")
                        raise ReservationFlowAbort("cancelled")
                    if "user" in follow_content:
                        return "user"
                    if "date" in follow_content:
                        return "date"
                    await self.ctx.send("Please type `user` or `date`, or `cancel` to abort.")
                continue
            await self.ctx.send("Please reply with `yes`, `no`, or `change` (or type `cancel`).")

    async def _next_message(self) -> discord.Message:
        if self._wait_for is None:
            raise ReservationFlowAbort("missing-wait-for")

        try:
            message = await self._wait_for(
                "message",
                timeout=PROMPT_TIMEOUT_SECONDS,
                check=lambda m: (
                    getattr(m.author, "id", None) == self._author_id
                    and getattr(m.channel, "id", None) == self._channel_id
                ),
            )
        except asyncio.TimeoutError:
            await self.ctx.send(
                "Reservation timed out. Please run `!reserve` again if you still need it."
            )
            raise ReservationFlowAbort("timeout")
        return message


def _display_name(member: object) -> Optional[str]:
    for attr in ("display_name", "nick", "name"):
        value = getattr(member, attr, None)
        if value:
            text = str(value).strip()
            if text:
                return text
    return None


def _resolve_member(guild: object, member_id: int):
    getter = getattr(guild, "get_member", None)
    if callable(getter):
        try:
            return getter(member_id)
        except Exception:  # pragma: no cover - defensive guard
            log.exception(
                "guild get_member failed",
                extra={"member_id": member_id},
            )
    return None


def _normalize_tag(tag: str | None) -> str:
    text = "" if tag is None else str(tag).strip().upper()
    return "".join(ch for ch in text if ch.isalnum())


def _parse_manual_open(row: list[str]) -> int:
    if len(row) <= 4:
        return 0
    return _to_int(row[4])


def _to_int(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"-?\d+", str(value))
    if not match:
        return 0
    try:
        return int(match.group(0))
    except ValueError:
        return 0


def _ticket_parent_ids() -> set[int]:
    parents: set[int] = set()
    for getter in (get_welcome_channel_id, get_promo_channel_id):
        value = getter()
        if value is None:
            continue
        try:
            parents.add(int(value))
        except (TypeError, ValueError):
            continue
    return parents


def _is_ticket_thread(channel: object) -> bool:
    if channel is None:
        return False

    channel_type = getattr(channel, "type", None)
    thread_types = {
        getattr(discord.ChannelType, "public_thread", None),
        getattr(discord.ChannelType, "private_thread", None),
        getattr(discord.ChannelType, "news_thread", None),
    }
    if channel_type not in thread_types:
        return False

    parent_id = getattr(channel, "parent_id", None)
    if parent_id is None:
        return False

    try:
        parent_value = int(parent_id)
    except (TypeError, ValueError):
        return False

    return parent_value in _ticket_parent_ids()


def _reservations_enabled() -> bool:
    for key in ("FEATURE_RESERVATIONS", "feature_reservations", "placement_reservations"):
        try:
            if feature_flags.is_enabled(key):
                return True
        except Exception:
            log.exception("feature toggle check failed", extra={"feature": key})
    return False


@dataclass(slots=True)
class _ThreadContext:
    ticket_code: str
    username: str
    thread: object
    guild: discord.Guild | None


def _normalize_date(value: dt.date | None) -> dt.date:
    if value is not None:
        return value
    return dt.date.max


def _reservation_sort_key(row: reservations.ReservationRow) -> tuple[dt.date, int]:
    return (_normalize_date(row.reserved_until), row.row_number)


def _reservation_display_date(reserved_until: dt.date | None) -> str:
    if reserved_until is None:
        return "unknown"
    return reserved_until.isoformat()


def _reservation_creator_display(guild: discord.Guild | None, recruiter_id: Optional[int]) -> str:
    if recruiter_id is None:
        return "unknown recruiter"
    if guild is not None:
        try:
            member = guild.get_member(recruiter_id)
        except Exception:  # pragma: no cover - guild lookup best effort
            member = None
        if member is not None and getattr(member, "mention", None):
            return getattr(member, "mention")
    return f"<@{recruiter_id}>"


def _reservation_user_display(
    guild: discord.Guild | None,
    row: reservations.ReservationRow,
    *,
    fallback_username: str,
) -> str:
    if row.ticket_user_id is not None:
        if guild is not None:
            try:
                member = guild.get_member(row.ticket_user_id)
            except Exception:  # pragma: no cover - guild lookup best effort
                member = None
            if member is not None and getattr(member, "mention", None):
                return getattr(member, "mention")
        return f"<@{row.ticket_user_id}>"
    snapshot = (row.username_snapshot or "").strip()
    if snapshot:
        return snapshot
    return fallback_username


def _reservation_status_display(status: str) -> str:
    status_text = (status or "").strip()
    if not status_text:
        return "status=unknown"
    return f"status={status_text}"


def _thread_recruit_display(
    guild: discord.Guild | None,
    rows: list[reservations.ReservationRow],
    *,
    parsed_username: str,
) -> str:
    for row in rows:
        display = _reservation_user_display(guild, row, fallback_username=parsed_username)
        if display:
            return display
    return parsed_username


def _thread_owner_id(thread: discord.Thread | None) -> Optional[int]:
    if thread is None:
        return None
    owner_id = getattr(thread, "owner_id", None)
    try:
        return int(owner_id) if owner_id is not None else None
    except (TypeError, ValueError):
        return None


def _parse_thread_context(channel: object) -> Optional[_ThreadContext]:
    if not _is_ticket_thread(channel):
        return None

    parts = parse_welcome_thread_name(getattr(channel, "name", None))
    if parts is None:
        return None

    return _ThreadContext(
        ticket_code=parts.ticket_code,
        username=parts.username,
        thread=channel,
        guild=getattr(channel, "guild", None),
    )


def _is_authorized(ctx: commands.Context) -> bool:
    return bool(is_recruiter(ctx) or is_admin_member(ctx))


class ReservationCog(commands.Cog):
    """Cog hosting reservation commands for recruitment staff."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @tier("staff")
    @help_metadata(
        function_group="recruitment",
        section="recruitment",
        access_tier="staff",
    )
    @commands.command(
        name="reserve",
        help="Reserve, release, or extend a clan seat for a recruit.",
        brief="Reservation management for a recruit.",
    )
    async def reserve(self, ctx: commands.Context, *args: str) -> None:
        if not args:
            await ctx.reply(
                "Usage: `!reserve <clantag>` (run inside the recruit's ticket thread).",
                mention_author=False,
            )
            return

        subcommand = (args[0] or "").strip()

        if subcommand.lower() == "release":
            await self._handle_release(ctx)
            return

        if subcommand.lower() == "extend":
            await self._handle_extend(ctx, args[1:] if len(args) > 1 else [])
            return

        if len(args) > 1:
            await ctx.reply(
                "Usage: `!reserve <clantag>` (run inside the recruit's ticket thread).",
                mention_author=False,
            )
            return

        clan_tag = subcommand

        if not _reservations_enabled():
            await ctx.reply(
                "Reservations are currently disabled. Please poke an admin if you think this is wrong.",
                mention_author=False,
            )
            return

        if ctx.guild is None:
            await ctx.reply(
                "⚠️ `!reserve` can only be used inside a server thread.",
                mention_author=False,
            )
            return

        if not (is_recruiter(ctx) or is_admin_member(ctx)):
            await ctx.reply(
                "Only Recruiters (or Admins) can reserve clan spots. If you need a hold, poke the Recruitment Crew.",
                mention_author=False,
            )
            return

        if not _is_ticket_thread(ctx.channel):
            await ctx.reply(
                "Please run `!reserve` inside the recruit’s ticket thread so I know who you’re talking about.",
                mention_author=False,
            )
            return

        clan_entry = recruitment.find_clan_row(clan_tag)
        if clan_entry is None:
            await ctx.reply(
                f"I don’t know the clan tag `{clan_tag}`. Please check the tag and try again.",
                mention_author=False,
            )
            return

        _, row = clan_entry
        sheet_tag = row[2] if len(row) > 2 and row[2] else clan_tag
        manual_open = _parse_manual_open(row)

        try:
            active_reservations = await reservations.count_active_reservations_for_clan(sheet_tag)
        except Exception:
            log.exception(
                "failed to count active reservations",
                extra={"clan_tag": _normalize_tag(sheet_tag)},
            )
            await ctx.reply(
                "Something went wrong while checking current reservations. Please try again later or contact an admin.",
                mention_author=False,
            )
            return

        wait_for = getattr(self.bot, "wait_for", None)
        if wait_for is None:
            await ctx.reply(
                "I can't start the reservation flow right now. Please try again later.",
                mention_author=False,
            )
            return

        conversation = ReservationConversation(
            ctx,
            clan_label=sheet_tag,
            manual_open=manual_open,
            active_reservations=active_reservations,
            wait_for=wait_for,
        )

        try:
            details = await conversation.run()
        except ReservationFlowAbort:
            return

        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        username_snapshot = details.ticket_username or details.ticket_display

        row_values = [
            str(getattr(ctx.channel, "id", "")),
            str(details.ticket_user_id or ""),
            str(getattr(ctx.author, "id", "")),
            sheet_tag,
            details.reserved_until.isoformat(),
            now.isoformat(),
            ACTIVE_STATUS,
            details.notes,
            username_snapshot or "",
        ]

        try:
            await reservations.append_reservation_row(row_values)
        except Exception:
            log.exception(
                "failed to append reservation row",
                extra={
                    "clan_tag": _normalize_tag(sheet_tag),
                    "thread_id": getattr(ctx.channel, "id", None),
                },
            )
            await ctx.send(
                "Something went wrong while saving the reservation to the sheet. No changes were made. Please try again or poke an admin."
            )
            return

        try:
            await availability.recompute_clan_availability(sheet_tag, guild=ctx.guild)
        except Exception:
            log.exception(
                "failed to recompute clan availability",
                extra={"clan_tag": _normalize_tag(sheet_tag)},
            )
            await ctx.send(
                "Saved the reservation, but I couldn't refresh clan availability. Please poke an admin to verify the sheet."
            )
            return

        fallback_reserved = active_reservations + 1
        fallback_available = max(manual_open - fallback_reserved, 0)

        updated_row = recruitment.get_clan_by_tag(sheet_tag)
        if updated_row is not None:
            ah_value = _safe_cell(updated_row, 33, fallback_reserved)
            af_value = _safe_cell(updated_row, 31, fallback_available)
        else:
            ah_value = str(fallback_reserved)
            af_value = str(fallback_available)

        await ctx.send(
            "\n".join(
                [
                    f"Reserved 1 spot in `{sheet_tag}` for {details.ticket_display} until `{details.reserved_until.isoformat()}`.",
                    f"Reserved for this clan: `{ah_value}`. Effective open spots: `{af_value}`.",
                ]
            )
        )

        thread = ctx.channel if isinstance(ctx.channel, discord.Thread) else None
        if thread is not None:
            try:
                await rename_thread_to_reserved(thread, sheet_tag)
            except Exception:
                log.exception(
                    "failed to rename welcome thread for reservation",
                    extra={
                        "thread_id": getattr(thread, "id", None),
                        "clan_tag": _normalize_tag(sheet_tag),
                    },
                )

        log.info(
            "[reserve] reservation created",
            extra={
                "clan_tag": _normalize_tag(sheet_tag),
                "thread_id": getattr(ctx.channel, "id", None),
                "recruiter_id": getattr(ctx.author, "id", None),
                "ticket_user_id": details.ticket_user_id,
                "reserved_until": details.reserved_until.isoformat(),
                "notes": details.notes,
            },
        )


    async def _handle_release(self, ctx: commands.Context) -> None:
        if not _reservations_enabled():
            await ctx.reply(
                "Reservations are currently disabled. Please poke an admin if you think this is wrong.",
                mention_author=False,
            )
            return

        if ctx.guild is None or not _is_authorized(ctx):
            await ctx.reply(
                "Only Recruiters (or Admins) can reserve clan spots. If you need a hold, poke the Recruitment Crew.",
                mention_author=False,
            )
            return

        if not _is_ticket_thread(ctx.channel):
            await ctx.reply(
                "Please run `!reserve` commands inside the recruit’s ticket thread so I know who you’re talking about.",
                mention_author=False,
            )
            return

        context = _parse_thread_context(ctx.channel)
        if context is None:
            await ctx.reply(
                "I couldn't figure out which recruit this thread is for. Please check the thread name and try again.",
                mention_author=False,
            )
            return

        owner_id = _thread_owner_id(context.thread)
        try:
            matches = await reservations.find_active_reservations_for_recruit(
                ticket_user_id=owner_id,
                username=context.username,
            )
        except Exception:
            log.exception(
                "failed to look up active reservations for release",
                extra={"ticket": context.ticket_code, "user": context.username},
            )
            await ctx.reply(
                "Something went wrong while checking reservations for this recruit. Please try again later.",
                mention_author=False,
            )
            return

        if not matches:
            await ctx.send(
                f"No active reservation found for {context.username}.",
                mention_author=False,
            )
            human_log.human(
                "warning",
                "⚠️ reservation_release — ticket=%s • user=%s • clan=none • result=not_found"
                % (context.ticket_code, context.username),
            )
            return

        matches.sort(key=_reservation_sort_key)
        if len(matches) > 1:
            log.warning(
                "multiple active reservations matched for release",
                extra={
                    "ticket": context.ticket_code,
                    "user": context.username,
                    "rows": [row.row_number for row in matches],
                },
            )

        target = matches[0]
        clan_tag = target.normalized_clan_tag or (target.clan_tag or "")

        try:
            await reservations.update_reservation_status(target.row_number, "released")
        except Exception:
            log.exception(
                "failed to update reservation status for release",
                extra={"row": target.row_number, "ticket": context.ticket_code},
            )
            await ctx.reply(
                "I couldn't mark the reservation as released. Please try again later or contact an admin.",
                mention_author=False,
            )
            return

        if clan_tag:
            try:
                await availability.adjust_manual_open_spots(clan_tag, 1)
            except Exception:
                log.exception(
                    "failed to adjust manual open spots after release",
                    extra={"clan_tag": clan_tag, "ticket": context.ticket_code},
                )
            try:
                await availability.recompute_clan_availability(clan_tag, guild=ctx.guild)
            except Exception:
                log.exception(
                    "failed to recompute availability after release",
                    extra={"clan_tag": clan_tag, "ticket": context.ticket_code},
                )

        recruit_display = _thread_recruit_display(ctx.guild, [target], parsed_username=context.username)
        display_tag = clan_tag or target.clan_tag or "the reserved clan"
        await ctx.send(
            f"Released the reserved seat in `{display_tag}` for {recruit_display} and returned it to the open pool."
        )

        human_log.human(
            "info",
            "🧭 reservation_release — ticket=%s • user=%s • clan=%s • result=ok • source=manual"
            % (context.ticket_code, context.username, display_tag),
        )


    async def _handle_extend(self, ctx: commands.Context, args: list[str]) -> None:
        if not args:
            await ctx.reply(
                "Usage: `!reserve extend <YYYY-MM-DD>` (run inside the recruit's ticket thread).",
                mention_author=False,
            )
            return

        if not _reservations_enabled():
            await ctx.reply(
                "Reservations are currently disabled. Please poke an admin if you think this is wrong.",
                mention_author=False,
            )
            return

        if ctx.guild is None or not _is_authorized(ctx):
            await ctx.reply(
                "Only Recruiters (or Admins) can reserve clan spots. If you need a hold, poke the Recruitment Crew.",
                mention_author=False,
            )
            return

        if not _is_ticket_thread(ctx.channel):
            await ctx.reply(
                "Please run `!reserve` commands inside the recruit’s ticket thread so I know who you’re talking about.",
                mention_author=False,
            )
            return

        context = _parse_thread_context(ctx.channel)
        if context is None:
            await ctx.reply(
                "I couldn't figure out which recruit this thread is for. Please check the thread name and try again.",
                mention_author=False,
            )
            return

        owner_id = _thread_owner_id(context.thread)
        try:
            matches = await reservations.find_active_reservations_for_recruit(
                ticket_user_id=owner_id,
                username=context.username,
            )
        except Exception:
            log.exception(
                "failed to look up active reservations for extend",
                extra={"ticket": context.ticket_code, "user": context.username},
            )
            await ctx.reply(
                "Something went wrong while checking reservations for this recruit. Please try again later.",
                mention_author=False,
            )
            return

        if not matches:
            await ctx.send(
                f"No active reservation found for {context.username}.",
                mention_author=False,
            )
            human_log.human(
                "warning",
                "⚠️ reservation_extend — ticket=%s • user=%s • clan=none • result=not_found"
                % (context.ticket_code, context.username),
            )
            return

        matches.sort(key=_reservation_sort_key)
        target = matches[0]
        if len(matches) > 1:
            log.warning(
                "multiple active reservations matched for extend",
                extra={
                    "ticket": context.ticket_code,
                    "user": context.username,
                    "rows": [row.row_number for row in matches],
                },
            )

        date_token = (args[0] or "").strip()
        try:
            new_date = dt.date.fromisoformat(date_token)
        except ValueError:
            new_date = None
        today = dt.date.today()
        if new_date is None or new_date < today:
            await ctx.reply(
                "Please provide a valid date in `YYYY-MM-DD` that is today or later.",
                mention_author=False,
            )
            human_log.human(
                "warning",
                "⚠️ reservation_extend — ticket=%s • user=%s • clan=%s • result=error • reason=invalid_date"
                % (
                    context.ticket_code,
                    context.username,
                    target.normalized_clan_tag or (target.clan_tag or "none"),
                ),
            )
            return

        try:
            await reservations.update_reservation_expiry(target.row_number, new_date)
        except Exception:
            log.exception(
                "failed to update reservation expiry",
                extra={"row": target.row_number, "ticket": context.ticket_code},
            )
            await ctx.reply(
                "Something went wrong while extending the reservation. Please try again later.",
                mention_author=False,
            )
            human_log.human(
                "error",
                "⚠️ reservation_extend — ticket=%s • user=%s • clan=%s • result=error • reason=update_failed"
                % (
                    context.ticket_code,
                    context.username,
                    target.normalized_clan_tag or (target.clan_tag or "none"),
                ),
            )
            return

        recruit_display = _thread_recruit_display(ctx.guild, [target], parsed_username=context.username)
        clan_label = target.normalized_clan_tag or (target.clan_tag or "the reserved clan")
        await ctx.send(
            f"Extended the reservation in `{clan_label}` for {recruit_display} until `{new_date.isoformat()}`."
        )

        human_log.human(
            "info",
            "🧭 reservation_extend — ticket=%s • user=%s • clan=%s • old=%s • new=%s • result=ok"
            % (
                context.ticket_code,
                context.username,
                clan_label,
                _reservation_display_date(target.reserved_until),
                new_date.isoformat(),
            ),
        )


    @tier("staff")
    @help_metadata(
        function_group="recruitment",
        section="recruitment",
        access_tier="staff",
    )
    @commands.command(
        name="reservations",
        help="List active reservations for a recruit or clan.",
        brief="Show active reservation details.",
    )
    async def reservations_command(self, ctx: commands.Context, clan_tag: str | None = None) -> None:
        if not _reservations_enabled():
            await ctx.reply(
                "Reservations are currently disabled. Please poke an admin if you think this is wrong.",
                mention_author=False,
            )
            return

        if ctx.guild is None or not _is_authorized(ctx):
            await ctx.reply(
                "Only Recruiters (or Admins) can inspect reservation details.",
                mention_author=False,
            )
            return

        if clan_tag is None or not str(clan_tag).strip():
            await self._handle_thread_reservations(ctx)
            return

        await self._handle_clan_reservations(ctx, clan_tag)


    async def _handle_thread_reservations(self, ctx: commands.Context) -> None:
        if not _is_ticket_thread(ctx.channel):
            await ctx.reply(
                "`!reservations` without a clan tag only works inside a recruit’s ticket thread.",
                mention_author=False,
            )
            return

        context = _parse_thread_context(ctx.channel)
        if context is None:
            await ctx.reply(
                "I couldn't parse this thread's ticket information. Please check the name and try again.",
                mention_author=False,
            )
            return

        owner_id = _thread_owner_id(context.thread)
        try:
            matches = await reservations.find_active_reservations_for_recruit(
                ticket_user_id=owner_id,
                username=context.username,
            )
        except Exception:
            log.exception(
                "failed to look up reservations for thread listing",
                extra={"ticket": context.ticket_code, "user": context.username},
            )
            await ctx.reply(
                "Something went wrong while loading reservations for this recruit. Please try again later.",
                mention_author=False,
            )
            human_log.human(
                "error",
                "⚠️ reservations_list — ticket=%s • user=%s • count=0 • scope=user • result=error • reason=lookup_failed"
                % (context.ticket_code, context.username),
            )
            return

        matches = [row for row in matches if row.is_active]
        matches.sort(key=_reservation_sort_key)

        recruit_display = _thread_recruit_display(ctx.guild, matches, parsed_username=context.username)

        if not matches:
            await ctx.send(f"No active reservations found for {recruit_display}.")
            human_log.human(
                "info",
                "🧭 reservations_list — ticket=%s • user=%s • count=0 • scope=user • result=empty"
                % (context.ticket_code, context.username),
            )
            return

        lines = [f"Active reservations for {recruit_display}:"]
        for row in matches:
            tag = row.normalized_clan_tag or (row.clan_tag or "?")
            creator = _reservation_creator_display(ctx.guild, row.recruiter_id)
            expiry = _reservation_display_date(row.reserved_until)
            details = [f"`{tag}` — expires {expiry}"]
            info_bits = [f"created by {creator}", _reservation_status_display(row.status)]
            details.append(f" ({' • '.join(info_bits)})")
            lines.append("• " + "".join(details))

        await ctx.send("\n".join(lines))

        human_log.human(
            "info",
            "🧭 reservations_list — ticket=%s • user=%s • count=%d • scope=user • result=ok"
            % (context.ticket_code, context.username, len(matches)),
        )


    async def _handle_clan_reservations(self, ctx: commands.Context, clan_tag: str) -> None:
        entry = recruitment.find_clan_row(clan_tag)
        if entry is None:
            await ctx.reply(
                f"I don’t know the clan tag `{clan_tag}`. Please check the tag and try again.",
                mention_author=False,
            )
            human_log.human(
                "warning",
                "⚠️ reservations_list — clan=%s • count=0 • scope=clan • result=error • reason=unknown_clan"
                % clan_tag,
            )
            return

        sheet_tag = entry[1][2] if len(entry[1]) > 2 and entry[1][2] else clan_tag

        try:
            rows = await reservations.get_active_reservations_for_clan(sheet_tag)
        except Exception:
            log.exception(
                "failed to fetch clan reservations",
                extra={"clan_tag": _normalize_tag(sheet_tag)},
            )
            await ctx.reply(
                "Something went wrong while loading reservations for that clan. Please try again later.",
                mention_author=False,
            )
            human_log.human(
                "error",
                "⚠️ reservations_list — clan=%s • count=0 • scope=clan • result=error • reason=lookup_failed"
                % sheet_tag,
            )
            return

        rows = [row for row in rows if row.is_active]
        rows.sort(key=_reservation_sort_key)

        if not rows:
            await ctx.send(f"No active reservations for `{sheet_tag}`.")
            human_log.human(
                "info",
                "🧭 reservations_list — clan=%s • count=0 • scope=clan • result=empty" % sheet_tag,
            )
            return

        lines = [f"Active reservations for `{sheet_tag}`:"]
        for row in rows:
            thread = await _resolve_thread(self.bot, row.thread_id)
            ticket_code = None
            username = row.username_snapshot or "unknown recruit"
            if thread is not None:
                parts = parse_welcome_thread_name(getattr(thread, "name", None))
                if parts is not None:
                    ticket_code = parts.ticket_code
                    if parts.username:
                        username = parts.username
            user_display = _reservation_user_display(ctx.guild, row, fallback_username=username)
            expiry = _reservation_display_date(row.reserved_until)
            ticket_label = ticket_code or "unknown"
            lines.append(
                f"• {user_display} — expires {expiry} (ticket {ticket_label})"
            )

        await ctx.send("\n".join(lines))

        human_log.human(
            "info",
            "🧭 reservations_list — clan=%s • count=%d • scope=clan • result=ok"
            % (sheet_tag, len(rows)),
        )


async def _resolve_thread(bot: commands.Bot, thread_id: str | int | None) -> Optional[object]:
    if thread_id is None:
        return None
    try:
        numeric_id = int(thread_id)
    except (TypeError, ValueError):
        return None

    getter = getattr(bot, "get_channel", None)
    if callable(getter):
        try:
            channel = getter(numeric_id)
        except Exception:  # pragma: no cover - cache lookup best effort
            channel = None
        if isinstance(channel, discord.Thread) or _is_ticket_thread(channel):
            return channel

    thread_getter = getattr(bot, "get_thread", None)
    if callable(thread_getter):
        try:
            channel = thread_getter(numeric_id)
        except Exception:  # pragma: no cover - cache lookup best effort
            channel = None
        if isinstance(channel, discord.Thread) or _is_ticket_thread(channel):
            return channel

    fetcher = getattr(bot, "fetch_channel", None)
    if callable(fetcher):
        try:
            channel = await fetcher(numeric_id)
        except Exception:
            channel = None
        if isinstance(channel, discord.Thread) or _is_ticket_thread(channel):
            return channel

    return None


def _safe_cell(row: list[str], index: int, fallback: int) -> str:
    if 0 <= index < len(row):
        value = row[index]
        text = str(value).strip()
        if text:
            return text
    return str(fallback)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReservationCog(bot))
    log.info("placement.reservations command loaded")


__all__ = ["ReservationCog", "setup"]
