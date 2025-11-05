"""Welcome-thread watcher that posts the onboarding questionnaire panel."""

from __future__ import annotations

import asyncio
import logging
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
)
from shared.logfmt import channel_label
from shared.logs import log_lifecycle

log = logging.getLogger("c1c.onboarding.welcome_watcher")

_TRIGGER_PHRASE = "awake by reacting with"
_TICKET_EMOJI = "🎫"


async def _send_runtime(message: str) -> None:
    try:
        await rt.send_log_message(message)
    except Exception:  # pragma: no cover - runtime notification best-effort
        log.warning("failed to send welcome watcher log message", exc_info=True)


async def _channel_readable_label(bot: commands.Bot, channel_id: int | str | None) -> str:
    if channel_id is None:
        return "#unknown"

    try:
        cid = int(channel_id)
    except (TypeError, ValueError):
        return f"#{channel_id}"

    import asyncio

    def _resolve_once() -> str | None:
        guilds: list[discord.Guild | None] = []
        channel = bot.get_channel(cid)
        if channel is not None:
            guilds.append(getattr(channel, "guild", None))
        guilds.extend(getattr(bot, "guilds", []))

        seen: set[int] = set()
        for guild in guilds:
            if guild is None:
                continue
            gid = getattr(guild, "id", None)
            if gid is not None:
                try:
                    gid_int = int(gid)
                except (TypeError, ValueError):
                    gid_int = None
                if gid_int is not None and gid_int in seen:
                    continue
                if gid_int is not None:
                    seen.add(gid_int)
            try:
                label = channel_label(guild, cid)
            except Exception:
                label = None
            if label and not label.startswith("#unknown"):
                return label

            resolved = guild.get_channel(cid)
            if resolved is not None:
                category = getattr(resolved, "category", None)
                name = getattr(resolved, "name", None)
                if category is not None and getattr(category, "name", None):
                    return f"#{category.name} › {name or 'channel'}"
                if name:
                    return f"#{name}"

            getter = getattr(guild, "get_thread", None)
            thread = getter(cid) if callable(getter) else None
            if isinstance(thread, discord.Thread):
                parent = getattr(thread, "parent", None)
                parent_name = getattr(parent, "name", None)
                thread_name = getattr(thread, "name", None) or "thread"
                if parent_name:
                    return f"#{parent_name} › {thread_name}"
                return f"#{thread_name}"
        return None

    fallback = f"#{cid}"
    for _ in range(20):  # up to ~5s total
        label = _resolve_once()
        if label:
            return label
        await asyncio.sleep(0.25)
    return fallback


def _announce(bot: commands.Bot, message: str, *, level: int = logging.INFO) -> None:
    log.log(level, "%s", message)

    async def runner() -> None:
        await bot.wait_until_ready()
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

    def __init__(self, bot: commands.Bot, *, channel_id: int) -> None:
        self.bot = bot
        self.channel_id = int(channel_id)
        coordinator_roles = get_recruitment_coordinator_role_ids()
        guardian_roles = get_guardian_knight_role_ids()
        self._staff_role_ids = set(coordinator_roles) | set(guardian_roles)
        self._onb_registered: bool = False
        self._onb_reg_error: str | None = None

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
        if thread.parent_id != self.channel_id:
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
        if thread.parent_id != self.channel_id or not thread_scopes.is_welcome_parent(thread):
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


async def setup(bot: commands.Bot) -> None:
    channel_id = get_welcome_channel_id()
    if not channel_id:
        _announce(bot, "📴 Welcome watcher disabled — WELCOME_CHANNEL_ID missing.")
        return
    if not feature_flags.is_enabled("welcome_dialog"):
        _announce(
            bot,
            "📴 Welcome watcher disabled — FeatureToggles['welcome_dialog'] is OFF.",
        )
        return
    if not feature_flags.is_enabled("recruitment_welcome"):
        _announce(
            bot,
            "📴 Welcome watcher disabled — FeatureToggles['recruitment_welcome'] is OFF.",
        )
        return

    watcher = WelcomeWatcher(bot, channel_id=channel_id)
    watcher._register_persistent_view()

    await bot.add_cog(watcher)

    if watcher._onb_registered:
        label = await _channel_readable_label(bot, channel_id)
        _announce(bot, f"✅ Welcome watcher enabled — channel={label}")
    else:
        reason = watcher._onb_reg_error or "unknown"
        _announce(bot, f"⚠️ Welcome watcher not enabled — reason={reason}", level=logging.WARNING)
