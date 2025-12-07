"""Shared environment accessors for CI scripts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return the value of an environment variable, with an optional default."""

    value = os.getenv(name)
    if value is None:
        return default
    return value


def get_env_path(name: str) -> Optional[Path]:
    """Return a ``Path`` for the environment variable if set."""

    value = get_env(name)
    if not value:
        return None
    return Path(value)


__all__ = ["get_env", "get_env_path"]

