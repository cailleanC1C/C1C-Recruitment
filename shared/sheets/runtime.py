"""Runtime helpers for coordinating Sheets package setup."""

from __future__ import annotations

__all__ = ["register_default_cache_buckets"]


def register_default_cache_buckets() -> None:
    """Register cache buckets required by Sheets modules."""

    from importlib import import_module

    onboarding_mod = import_module("shared.sheets.onboarding")
    recruitment_mod = import_module("shared.sheets.recruitment")

    onboarding_mod.register_cache_buckets()
    recruitment_mod.register_cache_buckets()
