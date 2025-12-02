"""C1C Leagues community autoposter and watcher."""

import logging

from .cog import LeaguesCog
from .scheduler import schedule_leagues_jobs

log = logging.getLogger("c1c.community.leagues")

__all__ = ["LeaguesCog", "schedule_leagues_jobs", "setup"]


async def setup(bot):
    await bot.add_cog(LeaguesCog(bot))
    log.info("C1C Leagues extension loaded")
