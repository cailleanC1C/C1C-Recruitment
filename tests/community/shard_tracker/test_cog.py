from __future__ import annotations

import asyncio
import asyncio
from unittest.mock import AsyncMock

import discord
from discord.ext import commands

from modules.community.shard_tracker import setup as shard_setup
from modules.community.shard_tracker.cog import ShardTracker
from modules.community.shard_tracker.data import ShardTrackerConfig


def test_resolve_kind_aliases():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    tracker = ShardTracker(bot)

    assert tracker._resolve_kind_key("Anc") == "ancient"
    assert tracker._resolve_kind("primals").key == "primal"
    assert tracker._resolve_kind("unknown") is None


def test_resolve_thread_rejects_wrong_channel(fake_discord_env):
    async def runner():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        tracker = ShardTracker(bot)
        config = ShardTrackerConfig(sheet_id="s", tab_name="t", channel_id=999)
        tracker.store.get_config = AsyncMock(return_value=config)

        guild = fake_discord_env.Guild()
        channel = fake_discord_env.TextChannel(channel_id=555, guild=guild)
        ctx = fake_discord_env.Context(fake_discord_env.User(42), channel)

        allowed, parent, thread = await tracker._resolve_thread(ctx)

        assert not allowed
        assert parent is None
        assert thread is None
        assert "Shard & Mercy tracking is only available" in ctx.replies[-1]

    asyncio.run(runner())


def test_resolve_thread_creates_and_reuses(fake_discord_env):
    async def runner():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        tracker = ShardTracker(bot)
        config = ShardTrackerConfig(sheet_id="s", tab_name="t", channel_id=444)
        tracker.store.get_config = AsyncMock(return_value=config)

        bot_stub = fake_discord_env.Bot()
        guild = fake_discord_env.Guild()
        guild.bot = bot_stub
        channel = fake_discord_env.TextChannel(channel_id=444, guild=guild, bot=bot_stub)
        user = fake_discord_env.User(55)
        ctx = fake_discord_env.Context(user, channel)

        allowed, parent, thread = await tracker._resolve_thread(ctx)
        assert allowed and thread is not None
        assert channel.created_names and len(channel.created_names) == 1

        allowed_again, _, thread_again = await tracker._resolve_thread(ctx)
        assert allowed_again
        assert thread_again is thread
        assert len(channel.created_names) == 1, "Thread should be reused"

    asyncio.run(runner())


def test_resolve_thread_rejects_foreign_thread(fake_discord_env):
    async def runner():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        tracker = ShardTracker(bot)
        config = ShardTrackerConfig(sheet_id="s", tab_name="t", channel_id=222)
        tracker.store.get_config = AsyncMock(return_value=config)

        bot_stub = fake_discord_env.Bot()
        guild = fake_discord_env.Guild()
        guild.bot = bot_stub
        channel = fake_discord_env.TextChannel(channel_id=222, guild=guild, bot=bot_stub)
        first_user = fake_discord_env.User(70)
        first_ctx = fake_discord_env.Context(first_user, channel)
        allowed, _, thread = await tracker._resolve_thread(first_ctx)
        assert allowed and thread is not None

        other_user = fake_discord_env.User(71)
        thread_ctx = fake_discord_env.Context(other_user, thread)
        allowed_second, _, thread_second = await tracker._resolve_thread(thread_ctx)

        assert not allowed_second
        assert thread_second is None
        assert "Please use your own shard thread" in thread_ctx.replies[-1]

    asyncio.run(runner())


def test_commands_are_registered():
    async def runner():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        await shard_setup(bot)
        assert bot.get_command("shards") is not None
        assert bot.get_command("mercy") is None

    asyncio.run(runner())


def test_legendary_reset_tracks_depth():
    tracker = ShardTracker(commands.Bot(command_prefix="!", intents=discord.Intents.none()))
    record = tracker.store._new_record([], 1, "user")  # type: ignore[arg-type]
    kind = tracker._resolve_kind("ancient")
    record.ancients_since_lego = 7

    tracker._apply_legendary_reset(record, kind)  # type: ignore[arg-type]

    assert record.ancients_since_lego == 0
    assert record.last_ancient_lego_depth == 7


def test_logged_mythic_resets_counters():
    tracker = ShardTracker(commands.Bot(command_prefix="!", intents=discord.Intents.none()))
    record = tracker.store._new_record([], 2, "user")  # type: ignore[arg-type]
    record.primals_since_mythic = 50

    tracker._apply_primal_mythical(record)  # type: ignore[arg-type]

    assert record.primals_since_mythic == 0
    assert record.primals_since_lego == 0
    assert record.last_primal_mythic_depth == 50
