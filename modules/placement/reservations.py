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
from modules.recruitment import availability
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


class ReservationCog(commands.Cog):
    """Cog hosting the `!reserve` recruiter command."""

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
        help="Reserve a clan seat for a recruit until a specific date.",
        brief="Reserve a clan seat for a recruit.",
    )
    async def reserve(self, ctx: commands.Context, clan_tag: str | None = None) -> None:
        if clan_tag is None or not str(clan_tag).strip():
            await ctx.reply(
                "Usage: `!reserve <clantag>` (run inside the recruit's ticket thread).",
                mention_author=False,
            )
            return

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
        row_values = [
            str(getattr(ctx.channel, "id", "")),
            str(details.ticket_user_id or ""),
            str(getattr(ctx.author, "id", "")),
            sheet_tag,
            details.reserved_until.isoformat(),
            now.isoformat(),
            ACTIVE_STATUS,
            details.notes,
            details.ticket_username or "",
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
