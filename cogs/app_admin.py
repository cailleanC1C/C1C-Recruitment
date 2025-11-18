"""App-level administrative commands registered under the cogs namespace."""

from __future__ import annotations

from discord.ext import commands

from c1c_coreops.helpers import help_metadata, tier
from c1c_coreops.rbac import admin_only
from modules.ops import server_map


class AppAdmin(commands.Cog):
    """Lightweight administrative utilities for bot operators."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        command = self.bot.get_command("ping")
        if command is None:
            return

        extras = getattr(command, "extras", None)
        if not isinstance(extras, dict):
            extras = {}
            setattr(command, "extras", extras)

        extras.setdefault("function_group", "operational")
        extras.setdefault("access_tier", "admin")

        try:
            setattr(command, "function_group", "operational")
        except Exception:
            pass
        try:
            setattr(command, "access_tier", "admin")
        except Exception:
            pass

        coreops = self.bot.get_cog("CoreOpsCog")
        apply_attrs = getattr(coreops, "_apply_metadata_attributes", None)
        if callable(apply_attrs):
            apply_attrs(command)

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.command(
        name="ping",
        hidden=True,
        help="Quick admin check to confirm the bot is responsive.",
    )
    @admin_only()
    async def ping(self, ctx: commands.Context) -> None:
        """React with a paddle to confirm the bot processed the request."""

        try:
            await ctx.message.add_reaction("🏓")
        except Exception:
            # Reaction failures are non-fatal (missing perms, deleted message, etc.).
            pass

    @tier("admin")
    @help_metadata(
        function_group="operational",
        section="utilities",
        access_tier="admin",
    )
    @commands.group(
        name="servermap",
        invoke_without_command=True,
        hidden=True,
        help="Admin tools for the automated #server-map post.",
    )
    @admin_only()
    async def servermap(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        await ctx.reply("Usage: !servermap refresh", mention_author=False)

    @servermap.command(
        name="refresh",
        help="Rebuild the #server-map channel immediately from the live guild structure.",
    )
    @admin_only()
    async def servermap_refresh(self, ctx: commands.Context) -> None:
        result = await server_map.refresh_server_map(self.bot, force=True, actor="command")
        if result.status == "ok":
            await ctx.reply(
                f"Server map refreshed — messages={result.message_count} • chars={result.total_chars}.",
                mention_author=False,
            )
            return
        if result.status == "disabled":
            await ctx.reply(
                "Server map automation is disabled. Set SERVER_MAP_ENABLED=true to enable it.",
                mention_author=False,
            )
            return
        reason = result.reason or "unknown"
        await ctx.reply(
            f"Server map refresh failed ({reason}). Check logs for details.",
            mention_author=False,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AppAdmin(bot))
