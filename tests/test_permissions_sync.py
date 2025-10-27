from __future__ import annotations

import asyncio
import types

import discord

from modules.ops.permissions_sync import BotAccessStore, BotPermissionManager
from modules.ops.watchers_permissions import BotPermissionWatcher


class FakeRole(discord.Object):
    def __init__(self, role_id: int, name: str) -> None:
        super().__init__(id=role_id)
        self.name = name


class FakeGuild:
    def __init__(self, guild_id: int = 1, name: str = "Test Guild") -> None:
        self.id = guild_id
        self.name = name
        self.roles = [FakeRole(10, "bot"), FakeRole(20, "other")]
        self._channels: list[FakeChannel] = []

    def add_channel(self, channel: "FakeChannel") -> None:
        self._channels.append(channel)

    @property
    def channels(self) -> list["FakeChannel"]:
        return list(self._channels)

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        for channel in self._channels:
            if channel.id == channel_id:
                return channel
        return None


class FakeChannel:
    def __init__(
        self,
        guild: FakeGuild,
        channel_id: int,
        name: str,
        *,
        channel_type: discord.ChannelType = discord.ChannelType.text,
        category: "FakeChannel | None" = None,
    ) -> None:
        self.guild = guild
        self.id = channel_id
        self.name = name
        self.type = channel_type
        self.category = category if channel_type != discord.ChannelType.category else None
        self.category_id = getattr(self.category, "id", None)
        self.overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
        guild.add_channel(self)

    async def set_permissions(
        self,
        role: discord.abc.Snowflake,
        *,
        overwrite: discord.PermissionOverwrite,
        reason: str | None = None,
    ) -> None:
        self.overwrites[role] = overwrite

    def overwrites_for(self, role: discord.abc.Snowflake) -> discord.PermissionOverwrite:
        return self.overwrites.get(role, discord.PermissionOverwrite())


class FakeCategory(FakeChannel):
    def __init__(self, guild: FakeGuild, channel_id: int, name: str) -> None:
        super().__init__(
            guild,
            channel_id,
            name,
            channel_type=discord.ChannelType.category,
            category=None,
        )


def test_sync_applies_allow_and_deny(tmp_path):
    store = BotAccessStore(tmp_path / "bot_access.json")
    bot = types.SimpleNamespace()
    manager = BotPermissionManager.for_bot(bot, store=store)
    guild = FakeGuild()
    category = FakeCategory(guild, 100, "Allowed")
    channel_allowed = FakeChannel(guild, 110, "ok", category=category)
    channel_denied = FakeChannel(guild, 120, "blocked", category=category)

    store.add_ids("categories", "allow", [category.id])
    store.add_ids("channels", "deny", [channel_denied.id])

    report = asyncio.run(
        manager.sync(
            guild,
            dry=False,
            include_voice=False,
            include_stage=False,
            write_csv=False,
        )
    )

    role = guild.roles[0]
    allow_overwrite = channel_allowed.overwrites[role]
    assert allow_overwrite.view_channel is True
    assert allow_overwrite.send_messages is True
    deny_overwrite = channel_denied.overwrites[role]
    assert deny_overwrite.view_channel is False
    assert report.counts["created"] == 3  # category + allow channel + deny channel


def test_sync_respects_manual_view_deny(tmp_path):
    store = BotAccessStore(tmp_path / "bot_access.json")
    bot = types.SimpleNamespace()
    manager = BotPermissionManager.for_bot(bot, store=store)
    guild = FakeGuild()
    channel = FakeChannel(guild, 210, "manual")

    store.add_ids("channels", "allow", [channel.id])
    role = guild.roles[0]
    channel.overwrites[role] = discord.PermissionOverwrite(view_channel=False)

    report = asyncio.run(
        manager.sync(
            guild,
            dry=False,
            include_voice=False,
            include_stage=False,
            write_csv=False,
        )
    )

    assert report.counts["skip_manual_deny"] == 1
    # Ensure overwrite untouched.
    assert channel.overwrites[role].view_channel is False


def test_watcher_applies_on_channel_create(tmp_path):
    store = BotAccessStore(tmp_path / "bot_access.json")
    bot = types.SimpleNamespace()
    manager = BotPermissionManager.for_bot(bot, store=store)
    guild = FakeGuild()
    category = FakeCategory(guild, 300, "Ops")
    store.add_ids("categories", "allow", [category.id])

    watcher = BotPermissionWatcher(bot)
    watcher.manager = manager

    channel = FakeChannel(guild, 310, "new-room", category=category)
    asyncio.run(watcher._apply_if_needed(channel, reason="create"))

    role = guild.roles[0]
    overwrite = channel.overwrites.get(role)
    assert overwrite is not None
    assert overwrite.view_channel is True
