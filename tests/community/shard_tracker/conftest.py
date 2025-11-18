from __future__ import annotations

from types import SimpleNamespace

import pytest
import discord
from c1c_coreops import helpers as helper_mod


_ORIGINAL_HELP_METADATA = helper_mod.help_metadata


def _patched_help_metadata(*args, **kwargs):
    kwargs.pop("help", None)
    return _ORIGINAL_HELP_METADATA(*args, **kwargs)


helper_mod.help_metadata = _patched_help_metadata


class FakeBot:
    def __init__(self) -> None:
        self._threads: dict[int, FakeThread] = {}

    def register_thread(self, thread: "FakeThread") -> None:
        self._threads[thread.id] = thread

    def get_channel(self, channel_id: int):  # pragma: no cover - helper passthrough
        return self._threads.get(channel_id)

    def get_thread(self, thread_id: int):  # pragma: no cover - helper passthrough
        return self._threads.get(thread_id)


class FakeGuild:
    def __init__(self, guild_id: int = 6500) -> None:
        self.id = guild_id
        self._threads: dict[int, FakeThread] = {}

    def register_thread(self, thread: "FakeThread") -> None:
        self._threads[thread.id] = thread

    def get_thread(self, thread_id: int):  # pragma: no cover - helper passthrough
        return self._threads.get(thread_id)


class FakeThread:
    def __init__(self, thread_id: int, parent: "FakeTextChannel", name: str) -> None:
        self.id = thread_id
        self.parent = parent
        self.guild = parent.guild
        self.name = name
        self.archived = False
        self.mention = f"<#{thread_id}>"
        self.messages: list[dict] = []

    async def send(self, *, embed=None, view=None):  # pragma: no cover - exercised via tests
        payload = {"embed": embed, "view": view}
        self.messages.append(payload)
        return payload


class FakeTextChannel:
    def __init__(self, channel_id: int, guild: FakeGuild, bot: FakeBot | None = None) -> None:
        self.id = channel_id
        self.guild = guild
        self._bot = bot
        self.threads: list[FakeThread] = []
        self._thread_seq = 0
        self.created_names: list[str] = []

    async def create_thread(
        self,
        *,
        name: str,
        type=None,
        invitable: bool,
        auto_archive_duration: int,
    ) -> FakeThread:  # pragma: no cover - exercised via tests
        self._thread_seq += 1
        thread = FakeThread(thread_id=10_000 + self._thread_seq, parent=self, name=name)
        self.threads.append(thread)
        self.created_names.append(name)
        self.guild.register_thread(thread)
        if self._bot:
            self._bot.register_thread(thread)
        return thread

    async def active_threads(self):  # pragma: no cover - exercised via tests
        return list(self.threads)


class FakeUser:
    def __init__(self, user_id: int, display_name: str = "Tester") -> None:
        self.id = user_id
        self.display_name = display_name
        self.name = display_name


class FakeContext:
    def __init__(self, author: FakeUser, channel) -> None:
        self.author = author
        self.channel = channel
        self.guild = channel.guild
        self.replies: list[str] = []

    async def reply(self, content: str, *, mention_author: bool = False) -> None:
        self.replies.append(content)


@pytest.fixture
def fake_discord_env(monkeypatch):
    env = SimpleNamespace(
        Bot=FakeBot,
        Guild=FakeGuild,
        Thread=FakeThread,
        TextChannel=FakeTextChannel,
        User=FakeUser,
        Context=FakeContext,
    )
    monkeypatch.setattr(discord, "TextChannel", FakeTextChannel, raising=False)
    monkeypatch.setattr(discord, "Thread", FakeThread, raising=False)
    return env


def pytest_unconfigure(config):  # pragma: no cover - test cleanup hook
    helper_mod.help_metadata = _ORIGINAL_HELP_METADATA
