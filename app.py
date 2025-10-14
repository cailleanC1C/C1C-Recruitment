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
    get_command_prefix,
    get_allowed_guild_ids,
    is_guild_allowed,
    get_config_snapshot,
)
from shared import socket_heartbeat as hb
from shared.runtime import Runtime
from shared.coreops_prefix import detect_admin_bang_command
from shared.coreops_rbac import (
    get_admin_role_ids,
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

runtime = Runtime(bot)


async def _enforce_guild_allow_list(
    *, log_when_empty: bool = False, log_success: bool = True
) -> bool:
    allowed_guilds = get_allowed_guild_ids()
    if not allowed_guilds:
        if log_when_empty:
            log.warning("Guild allow-list empty; gating disabled")
            await runtime.send_log_message("⚠️ Guild allow-list empty; gating disabled")
        return True

    unauthorized = [g for g in bot.guilds if not is_guild_allowed(g.id)]
    if unauthorized:
        names = ", ".join(f"{g.name} ({g.id})" for g in unauthorized)
        allowed_sorted = sorted(allowed_guilds)
        log.error(
            "Guild allow-list violation: %s. allowed=%s",
            names,
            allowed_sorted,
        )
        try:
            await runtime.send_log_message(
                "🚫 Guild allow-list violation: "
                f"{names}. allowed={allowed_sorted}"
            )
            await bot.close()
        finally:
            return False

    if log_success:
        allowed_sorted = sorted(allowed_guilds)
        connected_ids = [g.id for g in bot.guilds]
        log.info(
            "Guild allow-list verified",
            extra={
                "allowed": allowed_sorted,
                "connected": connected_ids,
            },
        )
        await runtime.send_log_message(
            "✅ Guild allow-list verified: "
            f"allowed={allowed_sorted} connected={connected_ids}"
        )
    return True


@bot.event
async def on_ready():
    hb.note_ready()
    log.info(
        "Bot ready as %s | env=%s | prefix=%s",
        bot.user,
        get_env_name(),
        BOT_PREFIX,
    )
    log.info(
        "CoreOps RBAC: admin_role_ids=%s staff_role_ids=%s",
        sorted(get_admin_role_ids()),
        sorted(get_staff_role_ids()),
        )
    bot._c1c_started_mono = _STARTED_MONO

    if not await _enforce_guild_allow_list(log_when_empty=True):
        return

    started, interval, stall, grace = runtime.watchdog(delay_sec=5.0)
    if started:
        async def announce() -> None:
            await asyncio.sleep(5.0)
            await runtime.send_log_message(
                "✅ Watchdog started — interval="
                f"{interval}s stall={stall}s disconnect_grace={grace}s"
            )

        runtime.scheduler.spawn(announce(), name="watchdog_announce")


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
async def on_guild_join(_guild: discord.Guild):
    hb.touch()
    await _enforce_guild_allow_list(log_success=False)


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
    try:
        await runtime.send_log_message(
            "⚠️ Command error: cmd="
            f"{getattr(ctx.command, 'name', None)} user={getattr(ctx.author, 'id', None)} err={error!r}"
        )
    except Exception:
        log.exception("failed to send command error to log channel")


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


CONFIG_META = {
    "source": "shared.config",
    "status": "ok",
    "loaded_at": None,
    "last_error": None,
}
CFG = get_config_snapshot()


async def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")
    try:
        await runtime.start(token)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
