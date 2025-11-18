from __future__ import annotations

import asyncio

from modules.community.shard_tracker.threads import ShardThreadRouter


def test_router_reuses_existing(fake_discord_env):
    async def runner():
        bot = fake_discord_env.Bot()
        guild = fake_discord_env.Guild()
        guild.bot = bot
        channel = fake_discord_env.TextChannel(channel_id=500, guild=guild, bot=bot)
        router = ShardThreadRouter(bot)
        user = fake_discord_env.User(1001)

        first_thread, created = await router.ensure_thread(parent=channel, user=user)
        assert created

        second_thread, second_created = await router.ensure_thread(parent=channel, user=user)
        assert not second_created
        assert second_thread is first_thread
        assert len(channel.threads) == 1

    asyncio.run(runner())


def test_router_skips_archived_thread(fake_discord_env):
    async def runner():
        bot = fake_discord_env.Bot()
        guild = fake_discord_env.Guild()
        guild.bot = bot
        channel = fake_discord_env.TextChannel(channel_id=501, guild=guild, bot=bot)
        router = ShardThreadRouter(bot)
        user = fake_discord_env.User(1002)

        thread, created = await router.ensure_thread(parent=channel, user=user)
        assert created
        thread.archived = True

        new_thread, new_created = await router.ensure_thread(parent=channel, user=user)
        assert new_created
        assert new_thread is not thread
        assert len(channel.threads) == 2

    asyncio.run(runner())


def test_router_owner_id_parses_from_name(fake_discord_env):
    async def runner():
        bot = fake_discord_env.Bot()
        guild = fake_discord_env.Guild()
        guild.bot = bot
        channel = fake_discord_env.TextChannel(channel_id=777, guild=guild, bot=bot)
        router = ShardThreadRouter(bot)
        user = fake_discord_env.User(55555)

        thread, _ = await router.ensure_thread(parent=channel, user=user)
        router._thread_owners.pop(thread.id, None)

        owner = router.owner_id_for(thread)
        assert owner == user.id

    asyncio.run(runner())
