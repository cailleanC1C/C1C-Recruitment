"""CoreOps module loader."""

from __future__ import annotations


async def setup(bot):
    from c1c_coreops.cog import CoreOpsCog

    await bot.add_cog(CoreOpsCog(bot))

