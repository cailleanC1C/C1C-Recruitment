"""Application runtime scaffolding for the unified bot process."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Optional

from aiohttp import web

from discord.ext import commands

from shared import socket_heartbeat as hb
from shared import health as health_srv
from shared.config import (
    get_port,
    get_env_name,
    get_bot_name,
    get_watchdog_stall_sec,
)

log = logging.getLogger("c1c.runtime")


class Scheduler:
    """Very small asyncio task supervisor for background jobs."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []

    def spawn(self, coro: Awaitable) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def shutdown(self) -> None:
        for task in self._tasks:
            if task.done():
                continue
            task.cancel()
        for task in self._tasks:
            if task.done():
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover - best-effort cleanup
                log.exception("scheduler task error during shutdown")


class Runtime:
    """Container object that wires the bot, health server, and scheduler."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.scheduler = Scheduler()
        self._health_site: Optional[web.TCPSite] = None

    async def start_health_server(self) -> None:
        if self._health_site is not None:
            return
        stall = get_watchdog_stall_sec()
        self._health_site = await health_srv.start_server(
            heartbeat_probe=hb.age_seconds,
            bot_name=get_bot_name(),
            env_name=get_env_name(),
            port=get_port(),
            stale_after_sec=stall,
        )
        log.info("health server listening", extra={"port": get_port(), "stall": stall})

    async def shutdown_health_server(self) -> None:
        if self._health_site is None:
            return
        try:
            await self._health_site.stop()
        finally:
            self._health_site = None

    async def load_extensions(self) -> None:
        """Load all feature modules into the shared bot instance."""

        from modules.coreops import cog as coreops_cog
        from recruitment import search as recruitment_search
        from recruitment import welcome as recruitment_welcome
        from onboarding import watcher_welcome as onboarding_welcome
        from onboarding import watcher_promo as onboarding_promo
        from ops import ops as ops_cog

        await coreops_cog.setup(self.bot)
        await recruitment_search.setup(self.bot)
        await recruitment_welcome.setup(self.bot)
        await onboarding_welcome.setup(self.bot)
        await onboarding_promo.setup(self.bot)
        await ops_cog.setup(self.bot)

    async def start(self, token: str) -> None:
        await self.start_health_server()
        await self.load_extensions()
        await self.bot.start(token)

    async def close(self) -> None:
        await self.shutdown_health_server()
        await self.scheduler.shutdown()
