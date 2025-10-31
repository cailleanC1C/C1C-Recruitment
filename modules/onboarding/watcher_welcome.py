"""Welcome-thread watcher that posts the onboarding questionnaire panel."""

from __future__ import annotations

import logging
import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from modules.common import feature_flags
from modules.common import runtime as rt
from modules.onboarding import logs, thread_scopes
from modules.onboarding.ui import panels
from shared.config import (
    get_guardian_knight_role_ids,
    get_recruitment_coordinator_role_ids,
    get_welcome_channel_id,
)

log = logging.getLogger("c1c.onboarding.welcome_watcher")

_TRIGGER_PHRASE = "awake by reacting with"
_TICKET_EMOJI = "🎫"


async def _send_runtime(message: str) -> None:
    try:
        await rt.send_log_message(message)
    except Exception:  # pragma: no cover - runtime notification best-effort
        log.warning("failed to send welcome watcher log message", exc_info=True)


def _announce(bot: commands.Bot, message: str) -> None:
    log.info("welcome watcher notice: %s", message)

    async def runner() -> None:
        await _send_runtime(message)

    bot.loop.create_task(runner())


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

    await bot.add_cog(WelcomeWatcher(bot, channel_id=channel_id))
    _announce(
        bot,
        f"✅ Welcome watcher enabled — channel_id={int(channel_id)}",
    )

*** End of File ***
