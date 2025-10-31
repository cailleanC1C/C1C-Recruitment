"""Runtime helpers for coordinating Sheets package setup."""

from __future__ import annotations

__all__ = ["register_default_cache_buckets"]


def register_default_cache_buckets() -> None:
    """Register cache buckets required by Sheets modules."""

    import shared.sheets.onboarding as onboarding
    import shared.sheets.recruitment as recruitment

    onboarding.register_cache_buckets()
    recruitment.register_cache_buckets()
