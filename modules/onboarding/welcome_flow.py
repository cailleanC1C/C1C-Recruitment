"""Shared entrypoint for onboarding welcome flows."""
from __future__ import annotations

import logging
from typing import Any

import discord

from modules.common import feature_flags
from c1c_coreops import rbac

from . import thread_scopes
from shared.sheets import onboarding_questions

__all__ = ["start_welcome_dialog"]


async def start_welcome_dialog(
    thread: discord.Thread,
    initiator: discord.abc.User | discord.Member | Any,
    source: str,
) -> None:
    """Launch the shared welcome dialog flow when all gates pass."""

    if not feature_flags.is_enabled("welcome_dialog"):
        logging.info("onboarding.welcome.start %s", {"skipped": "feature_disabled"})
        return

    if source != "ticket":
        if not initiator or not (
            rbac.is_admin_member(initiator) or rbac.is_recruiter(initiator)
        ):
            logging.info(
                "onboarding.welcome.start %s",
                {
                    "rejected": "scope_or_role",
                    "source": source,
                    "thread_id": getattr(thread, "id", None),
                },
            )
            return

    if not (
        thread_scopes.is_welcome_parent(thread)
        or thread_scopes.is_promo_parent(thread)
    ):
        logging.info(
            "onboarding.welcome.start %s",
            {
                "rejected": "scope_or_role",
                "source": source,
                "thread_id": getattr(thread, "id", None),
            },
        )
        return

    display_name = (
        getattr(initiator, "display_name", None)
        or getattr(initiator, "name", None)
        or ("system" if initiator is None else str(initiator))
    )
    marker_text = f"🧭 Dialog initiated by {display_name} via {source}"
    existing_markers = [
        message
        async for message in thread.history(limit=10)
        if marker_text in getattr(message, "content", "")
    ]
    if existing_markers:
        logging.info(
            "onboarding.welcome.start %s",
            {
                "skipped": "already_started",
                "source": source,
                "thread_id": getattr(thread, "id", None),
            },
        )
        return

    message = await thread.send(marker_text)
    try:
        await message.pin()
    except Exception:
        logging.exception(
            "onboarding.welcome.start failed to pin marker",
            extra={"thread_id": getattr(thread, "id", None)},
        )

    flow = "welcome" if thread_scopes.is_welcome_parent(thread) else "promo"
    schema_version: str | None = None
    questions = []
    try:
        questions = onboarding_questions.get_questions(flow)
        schema_version = onboarding_questions.schema_hash(flow)
    except Exception:
        logging.exception(
            "onboarding.welcome.start failed to load schema",
            extra={"thread_id": getattr(thread, "id", None), "flow": flow},
        )

    logging.info(
        "onboarding.welcome.start %s",
        {
            "mode": source,
            "guild_id": getattr(getattr(thread, "guild", None), "id", None),
            "parent_id": getattr(getattr(thread, "parent", None), "id", None),
            "thread_id": getattr(thread, "id", None),
            "by": (
                {"id": getattr(initiator, "id", None), "name": str(initiator)}
                if initiator
                else {"id": None, "name": "system"}
            ),
            "dedup": "created",
            "flow": flow,
            "schema_hash": schema_version,
            "questions": len(questions),
        },
    )

    await thread.send("(stub) dialog would launch here")
