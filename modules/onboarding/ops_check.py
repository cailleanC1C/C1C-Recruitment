# modules/onboarding/ops_check.py
from __future__ import annotations

from discord.ext import commands
from shared.logging import log


class OnboardingOps(commands.Cog):
    """No-op ops cog to keep runtime stable. No commands registered yet."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    """Load a minimal, crash-proof cog so runtime.load_extensions() succeeds."""
    await bot.add_cog(OnboardingOps(bot))
    log.info("onboarding.ops_check loaded (minimal, no commands)")
