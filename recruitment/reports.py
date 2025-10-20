"""Stub module for future recruitment reports integration."""

import logging


log = logging.getLogger(__name__)


async def setup(_bot) -> None:
    """Log that the reports stub has been loaded."""

    log.info("recruitment.reports stub loaded (no commands)")
