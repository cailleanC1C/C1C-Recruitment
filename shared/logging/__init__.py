"""Public logging helpers for the shared runtime package."""

from __future__ import annotations

from shared.logging.config import setup_logging
from shared.logging.structured import JsonFormatter, get_trace_id, set_trace_id

__all__ = ["JsonFormatter", "get_trace_id", "set_trace_id", "setup_logging"]

# --------------------------------------------------------------------
# Provide a default structured logger for backward-compatibility
# --------------------------------------------------------------------
import logging

log = logging.getLogger("c1c.shared")
__all__.append("log")
