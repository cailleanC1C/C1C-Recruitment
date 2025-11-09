"""Keepalive helper for periodic external pings."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Optional

import aiohttp
from discord.ext import commands

__all__ = ["ensure_started", "route_path"]

_TASK: asyncio.Task[None] | None = None
_URL: str | None = None
_INTERVAL: int | None = None


def route_path() -> str:
    """Return the configured keepalive route path for the local web app."""

    path = os.getenv("KEEPALIVE_PATH", "/keepalive").strip() or "/keepalive"
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _resolve_url() -> str:
    explicit = os.getenv("KEEPALIVE_URL", "").strip()
    if explicit:
        return explicit

    base = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    path = route_path()
    if base:
        return f"{base}{path}"

    port = os.getenv("PORT", "10000").strip() or "10000"
    return f"http://127.0.0.1:{port}{path}"


def _resolve_interval_seconds() -> int:
    raw = os.getenv("KEEPALIVE_INTERVAL", "300").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 300
    return max(60, value)


def _get_logger(bot: commands.Bot | None) -> logging.Logger:
    if bot is not None:
        logger = getattr(bot, "logger", None)
        if isinstance(logger, logging.Logger):
            return logger
    return logging.getLogger("modules.common.keepalive")


async def _runner(bot: commands.Bot, url: str, interval: int) -> None:
    logger = _get_logger(bot)
    jitter = max(0, interval // 10)
    timeout = aiohttp.ClientTimeout(total=10)
    logger.info("keepalive:task_started • url=%s • interval=%ss", url, interval)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                async with session.get(url) as resp:
                    status = resp.status
                    if 200 <= status < 300:
                        logger.info("keepalive:ping_ok • status=%s", status)
                    else:
                        logger.warning("keepalive:ping_fail • status=%s", status)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("keepalive:ping_fail • reason=%s", repr(exc))

            sleep_for = interval
            if jitter:
                sleep_for += random.randint(0, jitter)
            try:
                await asyncio.sleep(sleep_for)
            except asyncio.CancelledError:
                raise


async def ensure_started(
    bot: commands.Bot,
    *,
    url: Optional[str] = None,
    interval: Optional[int] = None,
) -> None:
    """Ensure the keepalive runner is active; restart if configuration changed."""

    global _TASK, _URL, _INTERVAL

    resolved_url = url or _resolve_url()
    resolved_interval = interval or _resolve_interval_seconds()

    task = _TASK
    if task is not None:
        if task.done():
            _TASK = None
            try:
                task.result()
            except Exception:
                pass
        elif _URL != resolved_url or _INTERVAL != resolved_interval:
            task.cancel()
            try:
                await task
            except Exception:
                pass
            _TASK = None

    if _TASK is None:
        loop = asyncio.get_running_loop()
        _TASK = loop.create_task(_runner(bot, resolved_url, resolved_interval), name="keepalive")
        _URL = resolved_url
        _INTERVAL = resolved_interval
