"""Helpers for identifying onboarding thread parents."""
from __future__ import annotations

from shared.config import get_promo_channel_id, get_welcome_channel_id

__all__ = [
    "is_welcome_parent",
    "is_promo_parent",
]


def is_welcome_parent(thread) -> bool:
    """Return ``True`` if the thread belongs to the configured welcome parent."""

    return getattr(thread, "parent_id", None) == get_welcome_channel_id()


def is_promo_parent(thread) -> bool:
    """Return ``True`` if the thread belongs to the configured promo parent."""

    return getattr(thread, "parent_id", None) == get_promo_channel_id()
