"""Compatibility wrapper for the cleanup housekeeping job."""

from modules.housekeeping.cleanup import (
    get_cleanup_interval_hours,
    get_cleanup_thread_ids,
    run_cleanup,
)

__all__ = [
    "get_cleanup_interval_hours",
    "get_cleanup_thread_ids",
    "run_cleanup",
]
