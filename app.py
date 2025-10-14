from __future__ import annotations

# app.py v0.1.0

import asyncio
import logging
import os
import time
from typing import Optional

import discord
from discord.abc import Messageable
from discord.ext import commands

from config.runtime import (
    get_port,
    get_env_name,
    get_bot_name,
    get_watchdog_stall_sec,
    get_watchdog_disconnect_grace_sec,
    get_keepalive_interval_sec,
    get_command_prefix,
    get_log_channel_id,
    get_refresh_times,
    get_timezone,
)
from shared import runtime as runtime_srv
from shared import socket_heartbeat as hb
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

LOG_CHANNEL_ID = get_log_channel_id()
REFRESH_TIMES = get_refresh_times()
REFRESH_TZ = get_timezone()

_watchdog_task: asyncio.Task | None = None
_schedule_task: asyncio.Task | None = None
_web_site: object | None = None

# ---- Discord client ---------------------------------------------------------

INTENTS = discord.Intents.default()
INTENTS.message_content = True  # needed for !ping smoke test
INTENTS.members = True

BOT_PREFIX = get_command_prefix()
COREOPS_COMMANDS = {"health", "digest", "env", "help", "ping"}

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
# Disable discord.py's default help so our CoreOps help can register
bot.remove_command("help")


async def _send_runtime_notice(message: str) -> None:
    if not LOG_CHANNEL_ID:
        return

    message_target: Messageable | None
    channel = bot.get_channel(LOG_CHANNEL_ID)
    message_target = channel if isinstance(channel, Messageable) else None
    if message_target is None:
        try:
            fetched = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception as exc:
            log.warning("Failed to fetch log channel %s: %s", LOG_CHANNEL_ID, exc)
            return
        if not isinstance(fetched, Messageable):
            log.warning("Log channel %s is not messageable (type=%s)", LOG_CHANNEL_ID, type(fetched))
            return
        message_target = fetched

    try:
        await message_target.send(message)
    except Exception as exc:
        log.warning("Failed to send runtime notice: %s", exc)

# ---- Watchdog & Scheduler ----------------------------------------------------

@bot.event
async def on_ready():
    global _watchdog_task, _schedule_task
    hb.note_ready()  # mark as fresh as soon as we're ready
    log.info(f"Bot ready as {bot.user} | env={get_env_name()} | prefix={BOT_PREFIX}")
    log.info(
        "CoreOps RBAC: admin_role_id=%s staff_role_ids=%s",
        get_admin_role_id(),
        sorted(get_staff_role_ids()),
    )
    bot._c1c_started_mono = _STARTED_MONO  # expose uptime for CoreOps

    if _watchdog_task is None or _watchdog_task.done():
        stall = get_watchdog_stall_sec()
        keepalive = get_keepalive_interval_sec()
        disconnect_grace = get_watchdog_disconnect_grace_sec(stall)
        _watchdog_task = runtime_srv.watchdog(
            heartbeat_probe=hb.age_seconds,
            check_sec=keepalive,
            stall_sec=stall,
            disconnect_grace=disconnect_grace,
            state_probe=hb.snapshot,
            latency_probe=lambda: latency_seconds(bot),
            start_delay=5,
            notify=_send_runtime_notice if LOG_CHANNEL_ID else None,
            label="Watchdog",
        )
        log.info(
            "Watchdog armed (stall_after=%ss, interval=%ss, disconnect_grace=%ss)",
            stall,
            keepalive,
            disconnect_grace,
        )

    if _schedule_task is None or _schedule_task.done():
        try:
            _schedule_task = runtime_srv.schedule_at_times(
                times_csv=REFRESH_TIMES,
                timezone_name=REFRESH_TZ,
                callback=_scheduled_refresh_placeholder,
                notify=_send_runtime_notice if LOG_CHANNEL_ID else None,
                label="Daily refresh",
            )
        except Exception as exc:
            log.error("Failed to arm scheduler: %s", exc)
            if LOG_CHANNEL_ID:
                await _send_runtime_notice(f"❌ Daily refresh disabled: {exc}")

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
    log.info(
        "seen msg: guild=%s chan=%s content=%r",
        getattr(message.guild, "id", None),
        getattr(message.channel, "id", None),
        message.content,
    )

    # Admin bang shortcuts: !health / !env / !digest / !help
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

# ---- Runtime placeholders ----------------------------------------------------

async def _scheduled_refresh_placeholder() -> None:
    log.debug("[schedule] Daily refresh placeholder (no-op)")

# ---- Main entry --------------------------------------------------------------
async def main():
    global _web_site
    _web_site = await runtime_srv.start_webserver(
        heartbeat_probe=hb.age_seconds,
        bot_name=get_bot_name(),
        env_name=get_env_name(),
        port=get_port(),
        stale_after_sec=get_watchdog_stall_sec(),
        state_probe=hb.snapshot,
        latency_probe=lambda: latency_seconds(bot),
        uptime_probe=uptime_seconds,
    )

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")
        
    # Load CoreOps cog (Phase 1)
    from modules.coreops import cog as coreops_cog
    await coreops_cog.setup(bot)
    log.info("CoreOps cog loaded successfully")

    # Login+run until closed. Watchdog starts in on_ready().
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
