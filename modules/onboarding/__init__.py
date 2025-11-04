"""Onboarding bootstrap utilities."""

from __future__ import annotations

import asyncio
from typing import Any

from discord.ext import commands

from modules.onboarding.startup import preload_onboarding_schema
from modules.onboarding.welcome_flow import start_welcome_dialog

__all__ = ["ensure_loaded", "setup", "start_welcome_dialog"]

_PRELOAD_TASK_ATTR = "_c1c_onboarding_preload_task"


async def ensure_loaded(bot: commands.Bot) -> commands.Bot:
    """No-op placeholder to keep legacy call sites operational."""

    return bot


async def setup(bot: commands.Bot) -> None:
    """Schedule the onboarding schema preload task."""

    existing: Any = getattr(bot, _PRELOAD_TASK_ATTR, None)
    done = getattr(existing, "done", None)
    if callable(done) and not done():
        return

    # discord.py 2.x removes direct access to ``Bot.loop``; schedule via asyncio
    task = asyncio.create_task(preload_onboarding_schema())
    setattr(bot, _PRELOAD_TASK_ATTR, task)
