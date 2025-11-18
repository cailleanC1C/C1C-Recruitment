"""Helpers for per-user shard tracker threads."""

from __future__ import annotations

import asyncio
import re
from typing import Dict, Tuple

import discord

_THREAD_OWNER_RE = re.compile(r"\[(\d{5,})]$")


class ShardThreadRouter:
    """Ensure each user receives a dedicated shard tracker thread."""

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self._user_threads: Dict[Tuple[int, int], int] = {}
        self._thread_owners: Dict[int, int] = {}
        self._lock = asyncio.Lock()

    async def ensure_thread(
        self, *, parent: discord.TextChannel, user: discord.abc.User
    ) -> tuple[discord.Thread, bool]:
        if not isinstance(parent, discord.TextChannel):
            raise TypeError("parent must be a TextChannel")
        async with self._lock:
            existing = await self._find_existing_thread(parent, user.id)
            if existing is not None:
                self._remember(existing, user.id)
                return existing, False
            thread = await parent.create_thread(
                name=self._build_thread_name(parent.guild, user),
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=10080,
            )
            self._remember(thread, user.id)
            return thread, True

    def owner_id_for(self, thread: discord.Thread | None) -> int | None:
        if thread is None:
            return None
        owner = self._thread_owners.get(thread.id)
        if owner:
            return owner
        parsed = self._parse_owner_from_name(thread.name)
        if parsed:
            self._thread_owners[thread.id] = parsed
        return parsed

    async def _find_existing_thread(
        self, parent: discord.TextChannel, user_id: int
    ) -> discord.Thread | None:
        guild_id = getattr(parent.guild, "id", None)
        if guild_id is not None:
            cached_id = self._user_threads.get((guild_id, user_id))
            if cached_id:
                thread = self._resolve_thread(parent.guild, cached_id)
                if self._is_viable_thread(thread):
                    return thread
        for thread in await self._list_candidate_threads(parent):
            owner = self._parse_owner_from_name(thread.name)
            if owner == user_id and self._is_viable_thread(thread):
                return thread
        return None

    async def _list_candidate_threads(
        self, parent: discord.TextChannel
    ) -> list[discord.Thread]:
        threads: list[discord.Thread] = []
        cached = getattr(parent, "threads", None)
        if isinstance(cached, list):
            threads.extend([t for t in cached if self._is_thread(t)])
        fetcher = getattr(parent, "active_threads", None)
        if callable(fetcher):
            try:
                fetched = await fetcher()
            except Exception:
                fetched = []
            else:
                threads.extend([t for t in fetched if self._is_thread(t)])
        return threads

    def _resolve_thread(
        self, guild: discord.Guild | None, thread_id: int
    ) -> discord.Thread | None:
        if guild is not None:
            thread = guild.get_thread(thread_id)
            if self._is_thread(thread):
                return thread
        if self.bot:
            channel = self.bot.get_channel(thread_id)
            if self._is_thread(channel):
                return channel
            getter = getattr(self.bot, "get_thread", None)
            if callable(getter):
                thread = getter(thread_id)
                if self._is_thread(thread):
                    return thread
        return None

    def _remember(self, thread: discord.Thread, owner_id: int) -> None:
        if thread.guild:
            self._user_threads[(thread.guild.id, owner_id)] = thread.id
        self._thread_owners[thread.id] = owner_id

    def _is_viable_thread(self, thread: discord.Thread | None) -> bool:
        if thread is None:
            return False
        if thread.archived:
            return False
        return True

    def _is_thread(self, obj: object | None) -> bool:
        if obj is None:
            return False
        if isinstance(obj, discord.Thread):
            return True
        return hasattr(obj, "id") and hasattr(obj, "archived")

    def _build_thread_name(
        self, guild: discord.Guild | None, user: discord.abc.User
    ) -> str:
        display = getattr(user, "display_name", None) or getattr(user, "name", "member")
        safe = " ".join(display.split())[:60]
        return f"Shards – {safe} [{getattr(user, 'id', 0)}]"

    def _parse_owner_from_name(self, name: str | None) -> int | None:
        if not name:
            return None
        match = _THREAD_OWNER_RE.search(name)
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None


__all__ = ["ShardThreadRouter"]

