import asyncio
import logging
from types import SimpleNamespace

import discord
from discord.ext import commands

from c1c_coreops.cog import CoreOpsCog, _CommandAccessResult


def test_can_display_command_logs_failures(monkeypatch, caplog):
    intents = discord.Intents.none()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    cog = CoreOpsCog(bot)

    async def fake_evaluate(_command, _ctx):
        return _CommandAccessResult(can_run=False, reason="blocked")

    monkeypatch.setattr(cog, "_evaluate_command_access", fake_evaluate)

    command = SimpleNamespace(qualified_name="ops test", name="test")
    ctx = SimpleNamespace()

    async def scenario() -> None:
        with caplog.at_level(logging.DEBUG):
            allowed = await cog._can_display_command(command, ctx, log_failures=True)
        assert not allowed

    asyncio.run(scenario())
    assert "ops test" in caplog.text
    assert "blocked" in caplog.text
