from __future__ import annotations

# app.py v0.1
import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from config.runtime import (
    get_port,
    get_env_name,
    get_bot_name,
    get_watchdog_stall_sec,
    get_command_prefix,
)
from shared import socket_heartbeat as hb
from shared import health as health_srv
from shared import watchdog

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("c1c.app")

# ---- Discord client ---------------------------------------------------------

INTENTS = discord.Intents.default()
INTENTS.message_content = True  # needed for !ping smoke test

BOT_PREFIX = get_command_prefix()

def _bang_prefixes():
    base = BOT_PREFIX
    return (f"!{base}", f"!{base} ")

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(*_bang_prefixes()),
    intents=INTENTS
)


_watchdog_started = False  # guard to start once


@bot.event
async def on_ready():
    global _watchdog_started
    hb.touch()  # mark as fresh as soon as we're ready
    log.info(f"Bot ready as {bot.user} | env={get_env_name()} | prefix={BOT_PREFIX}")

    if not _watchdog_started:
        stall = get_watchdog_stall_sec()
        asyncio.create_task(
            watchdog.run(hb.age_seconds, stall_after_sec=stall, check_every=30)
        )
        _watchdog_started = True
        log.info(f"Watchdog started (stall_after={stall}s)")


# Touch heartbeat on a few high-volume signals.
@bot.event
async def on_connect():
    hb.touch()

@bot.event
async def on_resumed():
    hb.touch()

@bot.event
async def on_message(message: discord.Message):
    hb.touch()
    await bot.process_commands(message)

# If your discord.py version supports it, this is the best “every packet” tap:
try:
    @bot.event
    async def on_socket_raw_receive(_):
        hb.touch()
except Exception:
    # older lib versions may not have this; the other events are enough
    pass


# ---- Minimal CoreOps smoke command ------------------------------------------

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.reply("pong")


# ---- Health server bootstrap -------------------------------------------------

async def boot_health_server():
    site = await health_srv.start_server(
        heartbeat_probe=hb.age_seconds,
        bot_name=get_bot_name(),
        env_name=get_env_name(),
        port=get_port(),
        stale_after_sec=get_watchdog_stall_sec(),
    )
    return site


# ---- Main entry --------------------------------------------------------------

async def main():
    # Start health server immediately so Render checks pass
    await boot_health_server()

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")

    # Login+run until closed. Watchdog starts in on_ready().
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
