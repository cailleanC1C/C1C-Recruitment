from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import discord
from discord.ext import commands

from shared.config import (
    get_env_name,
    get_bot_name,
    get_watchdog_stall_sec,
    get_watchdog_disconnect_grace_sec,
    get_keepalive_interval_sec,
    get_command_prefix,
)
from shared import socket_heartbeat as hb
from shared import watchdog
from shared.runtime import Runtime
from shared.coreops_prefix import detect_admin_bang_command
from shared.coreops_rbac import (
    get_admin_role_id,
    get_staff_role_ids,
    is_admin_member,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("c1c.app")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

BOT_PREFIX = get_command_prefix()
COREOPS_COMMANDS = {"health", "digest", "env", "help", "ping"}

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(
        f"!{BOT_PREFIX} ",
        f"!{BOT_PREFIX}",
        BOT_PREFIX,
        f"{BOT_PREFIX} ",
    ),
    intents=INTENTS,
)
bot.remove_command("help")

_watchdog_started = False


@bot.event
async def on_ready():
    global _watchdog_started
    hb.note_ready()
    log.info(
        "Bot ready as %s | env=%s | prefix=%s",
        bot.user,
        get_env_name(),
        BOT_PREFIX,
    )
    log.info(
        "CoreOps RBAC: admin_role_id=%s staff_role_ids=%s",
        get_admin_role_id(),
        sorted(get_staff_role_ids()),
    )
    bot._c1c_started_mono = _STARTED_MONO

    if not _watchdog_started:
        stall = get_watchdog_stall_sec()
        keepalive = get_keepalive_interval_sec()
        disconnect_grace = get_watchdog_disconnect_grace_sec(stall)
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


@bot.event
async def on_connect():
    hb.note_connected()


@bot.event
async def on_resumed():
    hb.note_connected()


@bot.event
async def on_socket_response(_payload):
    hb.touch()


try:
    @bot.event
    async def on_socket_raw_receive(_):
        hb.touch()
except Exception:
    pass


@bot.event
async def on_disconnect():
    hb.note_disconnected()


@bot.event
async def on_message(message: discord.Message):
    hb.touch()
    if bot.user and message.author.id == bot.user.id:
        return

    log.info(
        "seen msg: guild=%s chan=%s content=%r",
        getattr(message.guild, "id", None),
        getattr(message.channel, "id", None),
        message.content,
    )

    cmd_name = detect_admin_bang_command(
        message, commands=COREOPS_COMMANDS, is_admin=is_admin_member
    )
    if cmd_name:
        ctx = await bot.get_context(message)
        cmd = bot.get_command(cmd_name)
        if cmd is not None:
            ctx.command = cmd
            ctx.invoked_with = cmd_name
            await bot.invoke(ctx)
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    log.warning(
        "cmd error: cmd=%s user=%s err=%r",
        getattr(ctx.command, "name", None),
        getattr(ctx.author, "id", None),
        error,
    )


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    try:
        await ctx.message.add_reaction("🏓")
    except Exception:
        pass


BOT_VERSION = os.getenv("BOT_VERSION", "dev")
_STARTED_MONO = time.monotonic()


def uptime_seconds() -> float:
    return max(0.0, time.monotonic() - _STARTED_MONO)


def latency_seconds(bot: commands.Bot) -> Optional[float]:
    try:
        return float(getattr(bot, "latency", None)) if bot.latency is not None else None
    except Exception:
        return None


CONFIG_META = {"source": "runtime-only", "status": "ok", "loaded_at": None, "last_error": None}
CFG = {}


async def main() -> None:
    runtime = Runtime(bot)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")
    try:
        await runtime.start(token)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
