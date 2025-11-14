"""Welcome-thread watcher that posts the onboarding questionnaire panel."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from modules.common import feature_flags
from modules.common import runtime as rt
from modules.onboarding import logs, thread_membership, thread_scopes
from modules.onboarding.ui import panels
from shared.config import (
    get_guardian_knight_role_ids,
    get_recruitment_coordinator_role_ids,
    get_welcome_channel_id,
    get_ticket_tool_bot_id,
)
from shared.logfmt import channel_label
from shared.logs import log_lifecycle
from modules.recruitment import availability
from shared.sheets import onboarding as onboarding_sheets
from shared.sheets import reservations as reservations_sheets
from shared.sheets import recruitment as recruitment_sheets
from shared.sheets.cache_service import cache as sheets_cache

log = logging.getLogger("c1c.onboarding.welcome_watcher")

_TRIGGER_PHRASE = "awake by reacting with"
_TICKET_EMOJI = "🎫"

_THREAD_NAME_RE = re.compile(r"^W(?P<ticket>\d{4})[-_\s]*(?P<body>.+)$", re.IGNORECASE)
_CLOSED_MESSAGE_TOKEN = "ticket closed"
_NO_PLACEMENT_TAG = "NONE"
_WELCOME_HEADERS = ["ticket_number", "username", "clantag", "date_closed"]


@dataclass(slots=True)
class TicketContext:
    thread_id: int
    ticket_number: str
    username: str
    recruit_id: Optional[int] = None
    recruit_display: Optional[str] = None
    state: str = "open"
    prompt_message_id: Optional[int] = None
    final_clan: Optional[str] = None
    reservation_label: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ReservationDecision:
    label: str
    status: Optional[str]
    open_deltas: Dict[str, int]
    recompute_tags: List[str]


def _determine_reservation_decision(
    final_tag: str,
    reservation_row: reservations_sheets.ReservationRow | None,
    *,
    no_placement_tag: str,
    final_is_real: bool,
) -> ReservationDecision:
    normalized_final = (final_tag or "").strip().upper()
    open_deltas: Dict[str, int] = {}
    recompute: List[str] = []

    if reservation_row is None:
        if final_is_real and normalized_final and normalized_final != no_placement_tag:
            open_deltas[normalized_final] = -1
            recompute.append(normalized_final)
        return ReservationDecision("none", None, open_deltas, recompute)

    reservation_tag = reservation_row.normalized_clan_tag
    if not reservation_tag:
        reservation_tag = (reservation_row.clan_tag or "").strip().upper()

    if normalized_final == no_placement_tag:
        label = "cancelled"
        status = "cancelled"
        if reservation_tag:
            open_deltas[reservation_tag] = open_deltas.get(reservation_tag, 0) + 1
            recompute.append(reservation_tag)
        return ReservationDecision(label, status, open_deltas, recompute)

    if reservation_tag and reservation_tag == normalized_final:
        label = "same"
        status = "closed_same_clan"
        if reservation_tag:
            recompute.append(reservation_tag)
        return ReservationDecision(label, status, open_deltas, recompute)

    label = "moved"
    status = "closed_other_clan"
    if reservation_tag:
        open_deltas[reservation_tag] = open_deltas.get(reservation_tag, 0) + 1
        recompute.append(reservation_tag)
    if final_is_real and normalized_final and normalized_final != reservation_tag:
        open_deltas[normalized_final] = open_deltas.get(normalized_final, 0) - 1
        recompute.append(normalized_final)
    return ReservationDecision(label, status, open_deltas, recompute)


async def _send_runtime(message: str) -> None:
    try:
        await rt.send_log_message(message)
    except Exception:  # pragma: no cover - runtime notification best-effort
        log.warning("failed to send welcome watcher log message", exc_info=True)


def _channel_readable_label(bot: commands.Bot, channel_id: int | None) -> str:
    if channel_id is None:
        return "#unknown"
    try:
        cid = int(channel_id)
    except (TypeError, ValueError):
        return f"#{channel_id}"

    guild: discord.Guild | None = None
    channel = bot.get_channel(cid)
    if channel is not None:
        guild = getattr(channel, "guild", None)
    if guild is None:
        for candidate in getattr(bot, "guilds", []):
            try:
                if candidate.get_channel(cid):
                    guild = candidate
                    break
                getter = getattr(candidate, "get_thread", None)
                if callable(getter) and getter(cid):
                    guild = candidate
                    break
            except Exception:
                continue
    if guild is not None:
        try:
            return channel_label(guild, cid)
        except Exception:
            pass
    return f"#{cid}"


def _announce(bot: commands.Bot, message: str, *, level: int = logging.INFO) -> None:
    log.log(level, "%s", message)

    async def runner() -> None:
        await _send_runtime(message)

    # discord.py 2.x restricts accessing Client.loop here; schedule via asyncio
    asyncio.create_task(runner())


def _actor_id(actor: discord.abc.User | None) -> int | None:
    if actor is None:
        return None
    identifier = getattr(actor, "id", None)
    try:
        return int(identifier) if identifier is not None else None
    except (TypeError, ValueError):
        return None


def _collect_role_ids(member: discord.Member | None) -> set[int]:
    if member is None:
        return set()
    role_ids: set[int] = set()
    for role in getattr(member, "roles", ()) or ():
        rid = getattr(role, "id", None)
        if rid is None:
            continue
        try:
            role_ids.add(int(rid))
        except (TypeError, ValueError):
            continue
    return role_ids


class WelcomeWatcher(commands.Cog):
    """Gated watcher that attaches the persistent welcome questionnaire panel."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel_id: int | None = None
        coordinator_roles = get_recruitment_coordinator_role_ids()
        guardian_roles = get_guardian_knight_role_ids()
        self._staff_role_ids = set(coordinator_roles) | set(guardian_roles)
        self._onb_registered: bool = False
        self._onb_reg_error: str | None = None
        self._announced = False

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Guard against firing multiple times on reconnects
        if self._announced:
            return
        self._announced = True

        channel_id = get_welcome_channel_id()
        if not channel_id:
            _announce(self.bot, "📴 Welcome watcher disabled — WELCOME_CHANNEL_ID missing.")
            return

        try:
            channel_id_int = int(channel_id)
        except (TypeError, ValueError):
            self.channel_id = None
            _announce(
                self.bot,
                "⚠️ Welcome watcher not enabled — invalid WELCOME_CHANNEL_ID.",
                level=logging.WARNING,
            )
            return

        self.channel_id = channel_id_int

        if not feature_flags.is_enabled("welcome_dialog"):
            _announce(
                self.bot,
                "📴 Welcome watcher disabled — FeatureToggles['welcome_dialog'] is OFF.",
            )
            return

        if not feature_flags.is_enabled("recruitment_welcome"):
            _announce(
                self.bot,
                "📴 Welcome watcher disabled — FeatureToggles['recruitment_welcome'] is OFF.",
            )
            return

        self._register_persistent_view()

        if self._onb_registered:
            label = _channel_readable_label(self.bot, self.channel_id)
            _announce(self.bot, f"✅ Welcome watcher enabled — channel={label}")
        else:
            reason = self._onb_reg_error or "unknown"
            _announce(
                self.bot,
                f"⚠️ Welcome watcher not enabled — reason={reason}",
                level=logging.WARNING,
            )

    def _register_persistent_view(self) -> None:
        registration = panels.register_persistent_views(self.bot)

        view_name = registration.get("view") or "OpenQuestionsPanelView"
        components = registration.get("components") or "buttons:0,textinputs:0,selects:0"
        threads_default = registration.get("threads_default")
        duration_ms = registration.get("duration_ms")
        registered = bool(registration.get("registered"))
        duplicate = bool(registration.get("duplicate_registration"))
        error = registration.get("error")

        payload: dict[str, object] = {
            "view": view_name,
            "components": components,
            "result": "ok" if registered else "error",
        }
        if threads_default is not None:
            payload["threads_default"] = threads_default
        if isinstance(duration_ms, int):
            payload["duration"] = f"{duration_ms}ms"
        if duplicate:
            payload["duplicate_registration"] = True
        if error is not None:
            payload["reason"] = f"{error.__class__.__name__}: {error}"

        try:
            log_lifecycle(log, "onboarding", "view_registered", **payload)
        except Exception:
            pass

        if registered:
            self._onb_registered = True
            self._onb_reg_error = None
        else:
            reason = payload.get("reason")
            if isinstance(reason, str):
                self._onb_reg_error = reason
            else:
                self._onb_reg_error = "unknown"
            self._onb_registered = False

    # ---- helpers -----------------------------------------------------------------
    @staticmethod
    def _features_enabled() -> bool:
        return feature_flags.is_enabled("recruitment_welcome") and feature_flags.is_enabled(
            "welcome_dialog"
        )

    @staticmethod
    def _thread_owner_id(thread: discord.Thread | None) -> int | None:
        if thread is None:
            return None
        owner = getattr(thread, "owner", None)
        if isinstance(owner, discord.Member):
            return _actor_id(owner)
        raw = getattr(thread, "owner_id", None)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _eligible_member(self, member: discord.Member | None, thread: discord.Thread | None) -> bool:
        if member is None or thread is None:
            return False
        if getattr(member, "bot", False):
            return False
        try:
            perms = thread.permissions_for(member)
        except Exception:
            perms = None
        if perms is not None:
            can_post = getattr(perms, "send_messages_in_threads", None)
            if can_post is None:
                can_post = getattr(perms, "send_messages", False)
            if can_post:
                return True
        owner_id = self._thread_owner_id(thread)
        actor_id = _actor_id(member)
        if owner_id is not None and actor_id is not None and owner_id == actor_id:
            return True
        member_roles = _collect_role_ids(member)
        return bool(member_roles.intersection(self._staff_role_ids))

    def _log_context(
        self,
        thread: discord.Thread | None,
        actor: discord.abc.User | None,
        *,
        source: str,
        result: str,
        **extra: object,
    ) -> dict[str, object]:
        context = logs.thread_context(thread if isinstance(thread, discord.Thread) else None)
        context.update(
            {
                "view": "panel",
                "view_tag": panels.WELCOME_PANEL_TAG,
                "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "view_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "actor": logs.format_actor(actor if isinstance(actor, discord.abc.User) else None),
                "actor_name": logs.format_actor_handle(
                    actor if isinstance(actor, discord.abc.User) else None
                ),
                "app_permissions": "-",
                "app_perms_text": "-",
                "result": result,
                "source": source,
            }
        )
        if actor is not None:
            actor_identifier = _actor_id(actor)
            if actor_identifier is not None:
                context["actor_id"] = actor_identifier
        if extra:
            context.update(extra)
        return context

    async def _post_panel(
        self,
        thread: discord.Thread,
        *,
        actor: discord.abc.User | None,
        source: str,
    ) -> None:
        joined, join_error = await thread_membership.ensure_thread_membership(thread)
        if not joined:
            context = self._log_context(
                thread,
                actor,
                source=source,
                result="thread_join_failed",
                reason="thread_join",
            )
            if join_error is not None:
                await logs.send_welcome_exception("error", join_error, **context)
            else:
                await logs.send_welcome_log("error", **context)
            return

        view = panels.OpenQuestionsPanelView()
        content = "Ready when you are — tap below to open the onboarding questions."
        try:
            message = await thread.send(content, view=view)
        except Exception as exc:  # pragma: no cover - network
            await logs.send_welcome_exception(
                "error",
                exc,
                **self._log_context(thread, actor, source=source, result="error", reason="panel_send"),
            )
            return

        context = self._log_context(
            thread,
            actor,
            source=source,
            result="posted",
            message_id=getattr(message, "id", None),
            details={"view": "panel", "source": source},
        )
        if source == "emoji":
            context["emoji"] = _TICKET_EMOJI
        await logs.send_welcome_log("info", **context)

    # ---- listeners ----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._features_enabled():
            return
        thread = message.channel if isinstance(message.channel, discord.Thread) else None
        if thread is None:
            return
        target_channel_id = self.channel_id
        if target_channel_id is None or thread.parent_id != target_channel_id:
            return
        if not thread_scopes.is_welcome_parent(thread):
            return
        if not isinstance(message.author, (discord.Member, discord.User)):
            return
        if getattr(message.author, "bot", False):
            return

        try:
            thread_id_int = int(thread.id)
        except (TypeError, ValueError):
            thread_id_int = None
        controller = panels.get_controller(thread_id_int) if thread_id_int is not None else None
        handler = getattr(controller, "handle_rolling_message", None) if controller else None
        if callable(handler):
            try:
                handled = await handler(message)
            except Exception:
                log.warning("rolling card handler raised", exc_info=True)
            else:
                if handled:
                    return

        content = (message.content or "").lower()
        if _TRIGGER_PHRASE not in content:
            return

        try:
            await message.add_reaction("👍")
        except Exception:  # pragma: no cover - best effort
            log.debug("failed to add welcome auto-reaction", exc_info=True)

        await self._post_panel(thread, actor=message.author, source="phrase")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        if not self._features_enabled():
            return
        if str(payload.emoji) != _TICKET_EMOJI:
            return
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        thread = guild.get_thread(payload.channel_id)
        if thread is None:
            channel = self.bot.get_channel(payload.channel_id)
            thread = channel if isinstance(channel, discord.Thread) else None
        if thread is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:  # pragma: no cover - network fallback
                channel = None
            if isinstance(channel, discord.Thread):
                thread = channel
        if thread is None:
            return
        target_channel_id = self.channel_id
        if (
            target_channel_id is None
            or thread.parent_id != target_channel_id
            or not thread_scopes.is_welcome_parent(thread)
        ):
            return

        bot_user = getattr(self.bot, "user", None)
        if bot_user and payload.user_id == getattr(bot_user, "id", None):
            return

        member: discord.Member | None = payload.member
        if member is None and guild is not None:
            member = guild.get_member(payload.user_id)
        actor: discord.abc.User | None = member or payload.member

        if not self._eligible_member(member, thread):
            context = self._log_context(
                thread,
                actor,
                source="emoji",
                result="not_eligible",
                reason="missing_role_or_owner",
                emoji=_TICKET_EMOJI,
            )
            await logs.send_welcome_log("warn", **context)
            return

        await self._post_panel(thread, actor=actor, source="emoji")


class _ClanSelect(discord.ui.Select):
    def __init__(self, parent_view: "ClanSelectView") -> None:
        self._parent_view = parent_view
        super().__init__(placeholder="Select a clan tag", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI callback
        if not self.values:
            await interaction.response.defer()
            return
        await self._parent_view.handle_selection(interaction, self.values[0])


class ClanSelectView(discord.ui.View):
    def __init__(
        self,
        watcher: "WelcomeTicketWatcher",
        context: TicketContext,
        tags: List[str],
        *,
        page_size: int = 20,
    ) -> None:
        super().__init__(timeout=300)
        self.watcher = watcher
        self.context = context
        self.tags = [tag.strip().upper() for tag in tags if tag.strip()]
        self.page_size = max(1, page_size)
        self.page = 0
        self.message: Optional[discord.Message] = None

        self.select = _ClanSelect(self)
        self.add_item(self.select)

        self.prev_button = None
        self.next_button = None
        if len(self.tags) > self.page_size:
            self.prev_button = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary)
            self.prev_button.callback = self._on_prev  # type: ignore[assignment]
            self.next_button = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary)
            self.next_button.callback = self._on_next  # type: ignore[assignment]
            self.add_item(self.prev_button)
            self.add_item(self.next_button)

        self._refresh_options()

    def _page_slice(self) -> List[str]:
        start = self.page * self.page_size
        end = start + self.page_size
        return self.tags[start:end]

    def _refresh_options(self) -> None:
        page_tags = self._page_slice()
        if not page_tags:
            self.select.options = [
                discord.SelectOption(label="No clan tags available", value="none", default=True)
            ]
            self.select.disabled = True
        else:
            self.select.options = [discord.SelectOption(label=tag, value=tag) for tag in page_tags]
            self.select.disabled = False
        if self.prev_button is not None and self.next_button is not None:
            self.prev_button.disabled = self.page <= 0
            remaining = (self.page + 1) * self.page_size
            self.next_button.disabled = remaining >= len(self.tags)

    async def _on_prev(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI callback
        if self.page <= 0:
            await interaction.response.defer()
            return
        self.page -= 1
        self._refresh_options()
        await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI callback
        if (self.page + 1) * self.page_size >= len(self.tags):
            await interaction.response.defer()
            return
        self.page += 1
        self._refresh_options()
        await interaction.response.edit_message(view=self)

    async def handle_selection(self, interaction: discord.Interaction, tag: str) -> None:
        await interaction.response.defer()
        await self.watcher.finalize_from_interaction(self.context, tag, interaction, self)

    async def on_timeout(self) -> None:  # pragma: no cover - timeout path
        if self.message is None:
            return
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            log.debug("failed to disable clan select view on timeout", exc_info=True)


class WelcomeTicketWatcher(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        channel_id = get_welcome_channel_id()
        try:
            self.channel_id = int(channel_id) if channel_id is not None else None
        except (TypeError, ValueError):
            self.channel_id = None
        self.ticket_tool_id = get_ticket_tool_bot_id()
        self._tickets: Dict[int, TicketContext] = {}
        self._clan_tags: List[str] = []

        if self.channel_id is None:
            log.warning("welcome ticket watcher disabled — invalid WELCOME_CHANNEL_ID")

    @staticmethod
    def _features_enabled() -> bool:
        return feature_flags.is_enabled("recruitment_welcome")

    def _is_ticket_thread(self, thread: discord.Thread | None) -> bool:
        if thread is None:
            return False
        if self.channel_id is None:
            return False
        return getattr(thread, "parent_id", None) == self.channel_id

    def _parse_thread(self, name: str | None) -> Optional[tuple[str, str]]:
        if not name:
            return None
        match = _THREAD_NAME_RE.match(name.strip())
        if not match:
            return None
        ticket = match.group("ticket")
        body = (match.group("body") or "").strip()
        if not body:
            return None
        username_token = body.split()[0]
        username = username_token.split("-", 1)[0].strip(" -_")
        if not username:
            return None
        return ticket, username

    def _owner_matches(self, thread: discord.Thread) -> bool:
        if self.ticket_tool_id is None:
            return True
        owner_id = getattr(thread, "owner_id", None)
        try:
            owner_value = int(owner_id) if owner_id is not None else None
        except (TypeError, ValueError):
            owner_value = None
        return owner_value == self.ticket_tool_id

    def _is_ticket_tool(self, user: discord.abc.User | None) -> bool:
        if user is None:
            return False
        if self.ticket_tool_id is not None:
            return getattr(user, "id", None) == self.ticket_tool_id
        name = getattr(user, "name", "") or ""
        return "ticket" in name.lower() and "tool" in name.lower()

    async def _ensure_context(self, thread: discord.Thread) -> Optional[TicketContext]:
        context = self._tickets.get(thread.id)
        if context is not None:
            return context
        parsed = self._parse_thread(thread.name)
        if not parsed:
            return None
        ticket, username = parsed
        context = TicketContext(
            thread_id=thread.id,
            ticket_number=ticket,
            username=username,
            recruit_display=username,
        )
        self._tickets[thread.id] = context
        return context

    async def _handle_ticket_open(self, thread: discord.Thread, context: TicketContext) -> None:
        row = [context.ticket_number, context.username, "", ""]
        try:
            await asyncio.to_thread(onboarding_sheets.upsert_welcome, row, _WELCOME_HEADERS)
            log.info(
                "🧭 welcome_open — ticket=%s • user=%s", context.ticket_number, context.username
            )
        except Exception:
            log.exception(
                "failed to log welcome ticket open",
                extra={"thread_id": getattr(thread, "id", None), "ticket": context.ticket_number},
            )

    async def _load_clan_tags(self) -> List[str]:
        if self._clan_tags:
            return self._clan_tags

        tags: List[str] = []
        bucket = sheets_cache.get_bucket("clan_tags")
        if bucket is not None:
            value = bucket.value
            if not value:
                try:
                    await sheets_cache.refresh_now("clan_tags", actor="welcome_watcher")
                    value = bucket.value
                except Exception:
                    log.debug("failed to refresh clan_tags cache", exc_info=True)
            if isinstance(value, list):
                tags = [str(tag).strip().upper() for tag in value if str(tag or "").strip()]

        if not tags:
            try:
                tags = await asyncio.to_thread(onboarding_sheets.load_clan_tags)
                tags = [str(tag).strip().upper() for tag in tags if str(tag or "").strip()]
            except Exception:
                log.exception("failed to load clan tags from Sheets")
                return []

        unique = sorted({tag for tag in tags if tag})
        if _NO_PLACEMENT_TAG not in unique:
            unique.append(_NO_PLACEMENT_TAG)
        self._clan_tags = unique
        return self._clan_tags

    def _tag_known(self, tag: str) -> bool:
        normalized = (tag or "").strip().upper()
        return normalized in self._clan_tags

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not self._features_enabled():
            return
        if not self._is_ticket_thread(thread):
            return
        if not self._owner_matches(thread):
            return
        context = await self._ensure_context(thread)
        if context is None:
            return
        await self._handle_ticket_open(thread, context)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._features_enabled():
            return
        thread = message.channel if isinstance(message.channel, discord.Thread) else None
        if not self._is_ticket_thread(thread):
            return
        if thread is None:
            return
        context = await self._ensure_context(thread)
        if context is None:
            return

        if self._is_ticket_tool(message.author):
            content = (message.content or "").lower()
            if _CLOSED_MESSAGE_TOKEN in content and context.state not in {"awaiting_clan", "closed"}:
                await self._handle_ticket_closed(thread, context)
            return

        if getattr(message.author, "bot", False):
            return

        if context.state != "awaiting_clan" or context.final_clan:
            return

        candidate = (message.content or "").strip().upper()
        if not candidate:
            return
        await self._load_clan_tags()
        if not self._tag_known(candidate):
            return
        await self._finalize_clan_tag(
            thread,
            context,
            candidate,
            actor=message.author,
            source="message",
            prompt_message=None,
            view=None,
        )

    async def _handle_ticket_closed(self, thread: discord.Thread, context: TicketContext) -> None:
        tags = await self._load_clan_tags()
        if not tags:
            await thread.send(
                "⚠️ I couldn't load the clan tag list right now. Please try again in a moment."
            )
            log.warning(
                "⚠️ welcome_close — ticket=%s • user=%s • reason=clan_tags_unavailable",
                context.ticket_number,
                context.username,
            )
            return

        context.state = "awaiting_clan"
        content = (
            f"Which clan tag for {context.username} (ticket {context.ticket_number})?\n"
            "Pick one from the menu below, or simply type the tag as a message."
        )
        view = ClanSelectView(self, context, tags)
        try:
            message = await thread.send(content, view=view)
        except Exception:
            context.state = "open"
            log.exception(
                "failed to post clan selection prompt",
                extra={"thread_id": getattr(thread, "id", None), "ticket": context.ticket_number},
            )
            return
        view.message = message
        context.prompt_message_id = message.id

    async def finalize_from_interaction(
        self,
        context: TicketContext,
        tag: str,
        interaction: discord.Interaction,
        view: ClanSelectView,
    ) -> None:
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        if thread is None:
            await interaction.followup.send(
                "⚠️ I lost track of the ticket thread. Please try again.", ephemeral=True
            )
            return
        await self._finalize_clan_tag(
            thread,
            context,
            tag,
            actor=getattr(interaction, "user", None),
            source="select",
            prompt_message=interaction.message,
            view=view,
        )

    async def _finalize_clan_tag(
        self,
        thread: discord.Thread,
        context: TicketContext,
        final_tag: str,
        *,
        actor: discord.abc.User | None,
        source: str,
        prompt_message: Optional[discord.Message],
        view: Optional[ClanSelectView],
    ) -> None:
        if context.state == "closed":
            return

        final_tag = (final_tag or "").strip().upper() or _NO_PLACEMENT_TAG
        if final_tag != _NO_PLACEMENT_TAG:
            await self._load_clan_tags()
            if not self._tag_known(final_tag):
                await thread.send(
                    f"I don't recognise the clan tag `{final_tag}`. Please pick one from the menu or type a valid tag."
                )
                return

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = [context.ticket_number, context.username, final_tag, timestamp]

        try:
            result = await asyncio.to_thread(onboarding_sheets.upsert_welcome, row, _WELCOME_HEADERS)
        except Exception as exc:
            log.exception(
                "❌ welcome_close — ticket=%s • user=%s • final=%s • reason=sheet_write",
                context.ticket_number,
                context.username,
                final_tag,
            )
            await thread.send(
                "⚠️ Something went wrong while updating the onboarding log. Please try again later or contact an admin."
            )
            return

        row_missing = result != "updated"
        reservation_label = "none"
        actions_ok = True
        recompute_tags: List[str] = []

        final_entry = recruitment_sheets.find_clan_row(final_tag) if final_tag != _NO_PLACEMENT_TAG else None
        final_is_real = final_entry is not None

        reservation_row: reservations_sheets.ReservationRow | None = None
        if not row_missing:
            try:
                matches = await reservations_sheets.find_active_reservations_for_recruit(
                    context.recruit_id,
                    context.recruit_display or context.username,
                )
            except Exception:
                matches = []
                log.exception(
                    "failed to look up reservations for recruit",
                    extra={"ticket": context.ticket_number, "user": context.username},
                )
            if matches:
                reservation_row = matches[0]
                if len(matches) > 1:
                    log.warning(
                        "multiple active reservations matched",
                        extra={
                            "ticket": context.ticket_number,
                            "user": context.username,
                            "rows": [row.row_number for row in matches],
                        },
                    )

        decision = _determine_reservation_decision(
            final_tag,
            reservation_row,
            no_placement_tag=_NO_PLACEMENT_TAG,
            final_is_real=final_is_real,
        )
        reservation_label = decision.label

        if not row_missing and reservation_row is not None and decision.status:
            try:
                await reservations_sheets.update_reservation_status(
                    reservation_row.row_number, decision.status
                )
            except Exception:
                actions_ok = False
                log.exception(
                    "failed to update reservation status",
                    extra={
                        "row": reservation_row.row_number,
                        "ticket": context.ticket_number,
                        "status": decision.status,
                    },
                )

        if not row_missing:
            for tag, delta in decision.open_deltas.items():
                try:
                    await availability.adjust_manual_open_spots(tag, delta)
                except Exception:
                    actions_ok = False
                    log.exception(
                        "failed to adjust manual open spots",
                        extra={"clan_tag": tag, "delta": delta, "ticket": context.ticket_number},
                    )

            recompute_tags = decision.recompute_tags
            for tag in recompute_tags:
                try:
                    await availability.recompute_clan_availability(tag, guild=thread.guild)
                except Exception:
                    actions_ok = False
                    log.exception(
                        "failed to recompute clan availability",
                        extra={"clan_tag": tag, "ticket": context.ticket_number},
                    )

        final_display = final_tag if final_tag else _NO_PLACEMENT_TAG
        confirmation = (
            f"Got it — set clan tag to **{final_display}** and logged to the sheet. ✅"
        )
        if prompt_message is None and context.prompt_message_id:
            try:
                prompt_message = await thread.fetch_message(context.prompt_message_id)
            except Exception:
                prompt_message = None

        if prompt_message is not None:
            try:
                await prompt_message.edit(content=confirmation, view=None)
            except Exception:
                await thread.send(confirmation)
        else:
            await thread.send(confirmation)

        if view is not None:
            view.stop()

        try:
            new_name = f"Closed-{context.ticket_number}-{context.username}-{final_display}"
            await thread.edit(name=new_name)
        except Exception:
            actions_ok = False
            log.exception(
                "failed to rename welcome thread",
                extra={"thread_id": getattr(thread, "id", None), "ticket": context.ticket_number},
            )

        context.final_clan = final_display
        context.reservation_label = reservation_label
        context.state = "closed"

        if row_missing:
            log.warning(
                "⚠️ welcome_close — ticket=%s • user=%s • final=%s • reason=onboarding_row_missing",
                context.ticket_number,
                context.username,
                final_display,
            )
            return

        log_result = "ok" if actions_ok else "partial"
        log.info(
            "🧭 welcome_close — ticket=%s • user=%s • final=%s • reservation=%s • result=%s",
            context.ticket_number,
            context.username,
            final_display,
            reservation_label,
            log_result,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeWatcher(bot))
    await bot.add_cog(WelcomeTicketWatcher(bot))
