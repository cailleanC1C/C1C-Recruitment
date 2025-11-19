"""Tests for the server map text generator and gating helpers."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import discord

from modules.ops import server_map


class StubCategory:
    def __init__(self, name: str, position: int, category_id: int) -> None:
        self.name = name
        self.position = position
        self.id = category_id
        self.type = discord.ChannelType.category
        self.channels: list[StubChannel] = []


class StubChannel:
    def __init__(
        self,
        name: str,
        position: int,
        channel_id: int,
        channel_type: discord.ChannelType,
        category: StubCategory | None,
    ) -> None:
        self.name = name
        self.position = position
        self.id = channel_id
        self.type = channel_type
        self.category_id = getattr(category, "id", None)


def test_build_map_messages_renders_intro_mentions_and_headings() -> None:
    battle = StubCategory("BATTLE CHRONICLES", 1, 10)
    siege = StubChannel("siege", 1, 101, discord.ChannelType.text, battle)
    voice = StubChannel("voice-chat", 2, 102, discord.ChannelType.voice, battle)
    battle.channels.extend([siege, voice])

    halls = StubCategory("GATHERING HALLS", 2, 11)
    forum = StubChannel("forum-hq", 1, 103, discord.ChannelType.forum, halls)
    halls.channels.append(forum)

    lobby = StubChannel("lobby", 99, 104, discord.ChannelType.text, None)

    guild = SimpleNamespace(
        name="C1C",
        categories=[battle, halls],
        channels=[battle, halls, siege, voice, forum, lobby],
    )

    messages = server_map.build_map_messages(guild)

    expected = (
        "# 🧭 Server Map\n"
        "Tired of wandering the digital wilderness?\n"
        "Here’s your trusty compass—every channel, category, and secret nook laid out in one sleek guide.\n"
        "Ready to explore? Let’s go light the path together. ✨\n"
        "\n"
        "Channels with a 🔒 icon do need special roles to unlock access.\n"
        "\n"
        "🔹 <#104>\n"
        "\n"
        "## BATTLE CHRONICLES\n"
        "\n"
        "🔹 <#101>\n"
        "🔹 <#102>\n"
        "\n"
        "## GATHERING HALLS\n"
        "\n"
        "🔹 <#103>"
    )
    assert messages == [expected]


def test_build_map_messages_splits_when_threshold_hit() -> None:
    categories: list[StubCategory] = []
    guild_channels: list[object] = []
    for idx in range(3):
        category = StubCategory(f"Category {idx}", idx, idx + 1)
        channel = StubChannel(
            f"channel-{idx}",
            0,
            200 + idx,
            discord.ChannelType.text,
            category,
        )
        category.channels.append(channel)
        categories.append(category)
        guild_channels.extend([category, channel])

    guild = SimpleNamespace(categories=categories, channels=guild_channels)

    messages = server_map.build_map_messages(guild, threshold=40)

    assert len(messages) >= 2
    assert messages[0].startswith("# 🧭 Server Map")
    assert messages[-1].endswith("🔹 <#202>")


def test_build_map_messages_respects_blacklists() -> None:
    battle = StubCategory("BATTLE CHRONICLES", 1, 10)
    siege = StubChannel("siege", 1, 101, discord.ChannelType.text, battle)
    voice = StubChannel("voice-chat", 2, 102, discord.ChannelType.voice, battle)
    battle.channels.extend([siege, voice])

    halls = StubCategory("GATHERING HALLS", 2, 11)
    forum = StubChannel("forum-hq", 1, 103, discord.ChannelType.forum, halls)
    halls.channels.append(forum)

    lobby = StubChannel("lobby", 99, 104, discord.ChannelType.text, None)

    guild = SimpleNamespace(
        name="C1C",
        categories=[battle, halls],
        channels=[battle, halls, siege, voice, forum, lobby],
    )

    messages = server_map.build_map_messages(
        guild,
        category_blacklist={battle.id},
        channel_blacklist={voice.id, lobby.id},
    )

    assert len(messages) == 1
    body = messages[0]
    assert "## BATTLE CHRONICLES" not in body
    assert "🔹 <#102>" not in body
    assert "🔹 <#104>" not in body
    assert "## GATHERING HALLS" in body


def test_build_map_messages_lists_uncategorized_first() -> None:
    category = StubCategory("AFTER", 1, 10)
    alpha = StubChannel("alpha", 1, 101, discord.ChannelType.text, category)
    category.channels.append(alpha)
    lobby = StubChannel("lobby", 99, 104, discord.ChannelType.text, None)

    guild = SimpleNamespace(
        name="C1C",
        categories=[category],
        channels=[category, alpha, lobby],
    )

    messages = server_map.build_map_messages(guild)
    assert len(messages) == 1
    body = messages[0]
    assert body.index("🔹 <#104>") < body.index("## AFTER")


def test_should_refresh_enforces_interval() -> None:
    now = dt.datetime(2025, 11, 18, tzinfo=dt.timezone.utc)
    recent = now - dt.timedelta(days=5)
    assert not server_map.should_refresh(recent, refresh_days=30, now=now)
    older = now - dt.timedelta(days=45)
    assert server_map.should_refresh(older, refresh_days=30, now=now)
    assert server_map.should_refresh(None, refresh_days=30, now=now)
