"""Compatibility shim for legacy CoreOps help imports."""

from c1c_coreops.help import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]
