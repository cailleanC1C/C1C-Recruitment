# modules/onboarding/ops_check.py
from __future__ import annotations

from discord.ext import commands

from shared.logging import log


class OnboardingOps(commands.Cog):
    """No-op ops cog to keep runtime stable.
    We intentionally do not register any commands here yet.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # If we want a very simple ping later, add it here carefully.
    # For now, keep this cog side-effect free to avoid boot failures.


async def setup(bot: commands.Bot) -> None:
    """Load a minimal, crash-proof cog so runtime.load_extensions() succeeds."""
    await bot.add_cog(OnboardingOps(bot))
    log.human("info", "onboarding.ops_check loaded (minimal, no commands)")
