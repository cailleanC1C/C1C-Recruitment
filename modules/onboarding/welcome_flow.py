"""Shared entrypoint for onboarding welcome flows."""
from __future__ import annotations

from typing import Any, cast

import discord
from discord.ext import commands

from c1c_coreops import rbac
from modules.common import feature_flags
from modules.onboarding import logs

from modules.onboarding import thread_scopes
from modules.onboarding.controllers.promo_controller import PromoController
from modules.onboarding.controllers.welcome_controller import (
    WelcomeController,
    extract_target_from_message,
    locate_welcome_message,
)
from modules.onboarding.ui import panels
from shared.sheets import onboarding_questions

__all__ = ["start_welcome_dialog"]


async def start_welcome_dialog(
    thread: discord.Thread,
    initiator: discord.abc.User | discord.Member | Any,
    source: str,
    *,
    bot: commands.Bot | None = None,
    panel_message_id: int | None = None,
    panel_message: discord.Message | None = None,
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

    target_user_id: int | None = None
    target_message_id: int | None = None
    try:
        welcome_message = await locate_welcome_message(thread)
    except Exception as exc:  # pragma: no cover - defensive network path
        await logs.send_welcome_exception(
            "warn",
            exc,
            **_context({"result": "target_lookup_failed"}),
        )
    else:
        target_user_id, target_message_id = extract_target_from_message(welcome_message)

    if target_user_id is None:
        owner_id = getattr(thread, "owner_id", None) or getattr(thread, "starter_id", None)
        if owner_id is not None:
            try:
                target_user_id = int(owner_id)
            except (TypeError, ValueError):
                target_user_id = None

    context_defaults: dict[str, Any] = {}
    if target_user_id is not None:
        context_defaults["target_user_id"] = target_user_id
    if target_message_id is not None:
        context_defaults["target_message_id"] = target_message_id
    anchor_message_id: int | None = None
    if panel_message is not None:
        raw_id = getattr(panel_message, "id", None)
        try:
            anchor_message_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            anchor_message_id = None
    if panel_message_id is not None:
        context_defaults["message_id"] = panel_message_id
        if anchor_message_id is None:
            anchor_message_id = panel_message_id
    elif anchor_message_id is not None:
        context_defaults["message_id"] = anchor_message_id

    ambiguous_target = target_user_id is None
    context_defaults["ambiguous_target"] = ambiguous_target

    if flow == "welcome" and not feature_flags.is_enabled("recruitment_welcome"):
        await logs.send_welcome_log(
            "info",
            **_context(
                {
                    "result": "feature_disabled",
                    "reason": "recruitment_welcome",
                    **context_defaults,
                }
            ),
        )
        return

    if not feature_flags.is_enabled("welcome_dialog"):
        await logs.send_welcome_log(
            "info", **_context({"result": "feature_disabled", **context_defaults})
        )
        return

    if flow == "unknown":
        await logs.send_welcome_log(
            "warn",
            **_context({"result": "scope_gate", "reason": "scope_or_role", **context_defaults}),
        )
        return

    if source != "ticket":
        actor_id = getattr(actor, "id", None)
        actor_is_target = (
            actor_id is not None and target_user_id is not None and int(actor_id) == int(target_user_id)
        )
        actor_is_privileged = bool(
            initiator
            and (rbac.is_admin_member(initiator) or rbac.is_recruiter(initiator))
        )

        if not ambiguous_target and not (actor_is_target or actor_is_privileged):
            await logs.send_welcome_log(
                "warn",
                **_context(
                    {"result": "denied_role", "reason": "scope_or_role", **context_defaults},
                    actor_override=initiator if isinstance(initiator, (discord.Member, discord.User)) else None,
                ),
            )
            return

        if ambiguous_target and not actor_is_privileged:
            await logs.send_welcome_log(
                "info",
                **_context(
                    {"result": "ambiguous_target", **context_defaults},
                    actor_override=initiator if isinstance(initiator, (discord.Member, discord.User)) else None,
                ),
            )

    schema_version: str | None = None
    questions: list[Any] = []
    try:
        questions = onboarding_questions.get_questions(flow)
        schema_version = onboarding_questions.schema_hash(flow)
    except Exception as exc:
        await logs.send_welcome_exception(
            "error",
            exc,
            **_context({"result": "schema_load_failed", **context_defaults}),
        )
        return

    await logs.send_welcome_log(
        "info",
        **_context(
            {
                "result": "started",
                "schema": schema_version,
                "questions": len(questions),
                **context_defaults,
            }
        ),
    )

    controller_bot = bot or _resolve_bot(thread)
    if controller_bot is None:
        await logs.send_welcome_log(
            "warn",
            **_context({"result": "missing_bot", **context_defaults}),
        )
        return

    if flow == "welcome":
        controller = WelcomeController(controller_bot)
    else:
        controller = PromoController(controller_bot)
    if anchor_message_id is not None:
        try:
            controller._panel_messages[int(thread.id)] = int(anchor_message_id)
            panels.register_panel_message(int(thread.id), int(anchor_message_id))
        except (TypeError, ValueError):
            anchor_message_id = None
    if panel_message is not None and anchor_message_id is not None:
        controller._prefetched_panels[int(thread.id)] = panel_message
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
