"""Recruitment reporting module wiring."""

import logging


log = logging.getLogger(__name__)


async def setup(bot) -> None:
    """Register recruitment reporting commands and services."""

    from cogs import recruitment_reporting

    await recruitment_reporting.setup(bot)
    log.info("modules.recruitment.reports loaded (reporting enabled)")
