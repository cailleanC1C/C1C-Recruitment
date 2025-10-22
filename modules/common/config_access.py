"""Thin adapter exposing configuration helpers for modules-first imports."""

from __future__ import annotations

from shared import config as _config

__all__ = list(getattr(_config, "__all__", ()))

globals().update({name: getattr(_config, name) for name in __all__})
