"""Shared entrypoint for onboarding welcome flows."""
from __future__ import annotations

from typing import Any, cast

import discord
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import logs

from . import thread_scopes
from .controllers.promo_controller import PromoController
from .controllers.welcome_controller import WelcomeController
from shared.sheets import onboarding_questions

__all__ = ["start_welcome_dialog"]


async def start_welcome_dialog(
    thread: discord.Thread,
    initiator: discord.abc.User | discord.Member | Any,
    source: str,
    *,
    bot: commands.Bot | None = None,
) -> None:
    """Launch the shared welcome dialog flow when all gates pass."""

    flow = (
        "welcome"
        if thread_scopes.is_welcome_parent(thread)
        else "promo"
        if thread_scopes.is_promo_parent(thread)
        else "unknown"
    )
    actor = initiator if isinstance(initiator, (discord.Member, discord.User)) else None

    def _context(
        extra: dict[str, Any] | None = None,
        *,
        actor_override: discord.abc.User | discord.Member | None | object = ...,
    ) -> dict[str, Any]:
        resolved_actor = actor if actor_override is ... else cast(
            discord.abc.User | discord.Member | None, actor_override
        )
        payload = logs.thread_context(thread)
        payload["flow"] = flow
        payload["source"] = source
        payload["actor"] = logs.format_actor(resolved_actor)
        handle = logs.format_actor_handle(resolved_actor)
        if handle:
            payload["actor_name"] = handle
        if extra:
            payload.update(extra)
        return payload

    if not feature_flags.is_enabled("welcome_dialog"):
        await logs.send_welcome_log("info", **_context({"result": "feature_disabled"}))
        return

    if source != "ticket":
        if not initiator or not (
            rbac.is_admin_member(initiator) or rbac.is_recruiter(initiator)
        ):
            await logs.send_welcome_log(
                "warn",
                **_context(
                    {"result": "role_gate", "reason": "scope_or_role"},
                    actor_override=initiator if isinstance(initiator, (discord.Member, discord.User)) else None,
                ),
            )
            return

    if flow == "unknown":
        await logs.send_welcome_log(
            "warn",
            **_context({"result": "scope_gate", "reason": "scope_or_role"}),
        )
        return

    schema_version: str | None = None
    questions: list[Any] = []
    try:
        questions = onboarding_questions.get_questions(flow)
        schema_version = onboarding_questions.schema_hash(flow)
    except Exception as exc:
        await logs.send_welcome_exception(
            "error",
            exc,
            **_context({"result": "schema_load_failed"}),
        )
        return

    await logs.send_welcome_log(
        "info",
        **_context({"result": "started", "schema": schema_version, "questions": len(questions)}),
    )

    controller_bot = bot or _resolve_bot(thread)
    if controller_bot is None:
        await logs.send_welcome_log(
            "warn",
            **_context({"result": "missing_bot"}),
        )
        return

    if flow == "welcome":
        controller = WelcomeController(controller_bot)
    else:
        controller = PromoController(controller_bot)
    await controller.run(
        thread,
        actor,
        schema_version,
        questions,
        source=source,
    )


def _resolve_bot(thread: discord.Thread) -> commands.Bot | None:
    state = getattr(thread, "_state", None)
    if state is None:
        guild = getattr(thread, "guild", None)
        state = getattr(guild, "_state", None)
    if state is None:
        return None
    client = getattr(state, "_get_client", None)
    if callable(client):
        bot = client()
        if isinstance(bot, commands.Bot):
            return bot
    bot = getattr(state, "client", None)
    if isinstance(bot, commands.Bot):
        return bot
    return None
