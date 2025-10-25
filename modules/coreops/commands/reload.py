"""CoreOps reload command helpers."""

from __future__ import annotations

import inspect
import logging

from discord.ext import commands

from modules.common import runtime

logger = logging.getLogger("c1c.coreops.commands.reload")

bot: commands.Bot | None = None


def _set_bot(value: commands.Bot) -> None:
    global bot
    bot = value


def _get_bot() -> commands.Bot | None:
    return bot


async def _maybe_await(result: object) -> None:
    if inspect.isawaitable(result):
        await result  # type: ignore[arg-type]


async def _invoke_bot_method(name: str) -> None:
    bot = _get_bot()
    if bot is None:
        logger.debug("skip %s: bot not registered", name)
        return
    method = getattr(bot, name, None)
    if method is None:
        logger.debug("skip %s: missing attribute", name)
        return
    try:
        await _maybe_await(method())
    except Exception:
        logger.exception("%s raised during reload", name)
        raise


async def _handle_reboot() -> None:
    """Perform the reboot side effects for ``!reload --reboot``."""

    await runtime.recreate_http_app()
    await _invoke_bot_method("reload_extensions")
    await _invoke_bot_method("start_reconnect_cycle")
    logger.info("Runtime rebooted via !reload --reboot")


class Reload(commands.Cog):
    """Reload command wiring."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        _set_bot(bot)

    @commands.command(name="reload")
    async def reload_command(self, ctx: commands.Context, *flags: str) -> None:
        reboot = any(flag == "--reboot" for flag in flags)
        runtime.reload_config()
        message = "✅ Configuration reloaded."
        if reboot:
            try:
                await _handle_reboot()
            except Exception as exc:  # pragma: no cover - surfaced to command invoker
                await ctx.send(f"⚠️ Reload failed: {exc}")
                raise
            else:
                message = "✅ Reloaded configuration and rebooted runtime."
        await ctx.send(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reload(bot))
