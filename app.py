from __future__ import annotations

# app.py v0.1.0

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
    get_watchdog_disconnect_grace_sec,
    get_keepalive_interval_sec,
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
    command_prefix=commands.when_mentioned_or(
        f"!{get_command_prefix()} ",  # with space
        f"!{get_command_prefix()}",   # without space
        get_command_prefix(),         # plain (no bang)
        f"{get_command_prefix()} "    # plain with space
    ),
    intents=INTENTS,
)

# ---- Watchdog -----------------------------------------------
_watchdog_started = False  # guard to start once

@bot.event
async def on_ready():
    global _watchdog_started
    hb.note_ready()  # mark as fresh as soon as we're ready
    log.info(f"Bot ready as {bot.user} | env={get_env_name()} | prefix={BOT_PREFIX}")
    bot._c1c_started_mono = _STARTED_MONO  # expose uptime for CoreOps

    if not _watchdog_started:
        stall = get_watchdog_stall_sec()
        keepalive = get_keepalive_interval_sec()
        disconnect_grace = get_watchdog_disconnect_grace_sec(stall)
        # small grace so the gateway settles before we start enforcing staleness
        await asyncio.sleep(5)
        asyncio.create_task(
            watchdog.run(
                hb.age_seconds,
                stall_after_sec=stall,
                check_every=keepalive,
                state_probe=hb.snapshot,
                disconnect_grace_sec=disconnect_grace,
                latency_probe=lambda: getattr(bot, "latency", None),
            )
        )
        _watchdog_started = True
        log.info(
            "Watchdog started (stall_after=%ss, interval=%ss, disconnect_grace=%ss)",
            stall,
            keepalive,
            disconnect_grace,
        )

# Touch heartbeat on a few high-volume signals.
@bot.event
async def on_connect():
    hb.note_connected()

@bot.event
async def on_resumed():
    hb.note_connected()

@bot.event
async def on_socket_response(payload):
    # Fires for every gateway event; guarantees our heartbeat stays fresh.
    hb.touch()

# If your discord.py version supports it, this is the best “every packet” tap:
try:
    @bot.event
    async def on_socket_raw_receive(_):
        hb.touch()
except Exception:
    # older lib versions may not have this; the other events are enough
    pass


@bot.event
async def on_disconnect():
    hb.note_disconnected()

@bot.event
async def on_message(message: discord.Message):
    hb.touch()
    if bot.user and message.author.id == bot.user.id:
        return
    # TEMP: visibility probe
    log.info(f"seen msg: guild={getattr(message.guild,'id',None)} "
             f"chan={getattr(message.channel,'id',None)} content={message.content!r}")
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    log.warning(f"cmd error: cmd={getattr(ctx.command,'name',None)} "
                f"user={ctx.author.id} err={error!r}")

# ---- Minimal CoreOps smoke command ------------------------------------------
@bot.command(name="ping")
async def ping(ctx):
    try:
        await ctx.message.add_reaction("🏓")
    except Exception:
        pass

# ---- CoreOps shims (Phase 1) -----------------------------------------------
import time
from typing import Optional

BOT_VERSION = os.getenv("BOT_VERSION", "dev")
_STARTED_MONO = time.monotonic()

def uptime_seconds() -> float:
    return max(0.0, time.monotonic() - _STARTED_MONO)

def latency_seconds(bot) -> Optional[float]:
    try:
        return float(getattr(bot, "latency", None)) if bot.latency is not None else None
    except Exception:
        return None

# Config placeholders for Phase 1 (no Sheets yet)
CONFIG_META = {"source": "runtime-only", "status": "ok", "loaded_at": None, "last_error": None}
CFG = {}

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
        
    # Load CoreOps cog (Phase 1)
    from modules.coreops import cog as coreops_cog
    await coreops_cog.setup(bot)

    # Login+run until closed. Watchdog starts in on_ready().
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
