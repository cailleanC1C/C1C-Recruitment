"""Log helpers for CoreOps lifecycle messaging."""

from __future__ import annotations

from shared import logfmt

LIFECYCLE_PREFIX = f"{logfmt.LOG_EMOJI['lifecycle']} **CoreOps** —"


def lifecycle_tag() -> str:
    """Return the lifecycle log prefix following DocStyle logging rules."""

    return LIFECYCLE_PREFIX


__all__ = ("LIFECYCLE_PREFIX", "lifecycle_tag")
