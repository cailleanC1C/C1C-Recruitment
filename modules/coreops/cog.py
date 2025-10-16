"""CoreOps module loader."""

from __future__ import annotations


async def setup(bot):
    from shared.coreops_cog import CoreOpsCog

    await bot.add_cog(CoreOpsCog(bot))

