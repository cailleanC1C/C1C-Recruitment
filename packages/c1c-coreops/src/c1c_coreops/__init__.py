"""CoreOps helpers packaged for internal reuse."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Iterable

__all__ = ("cog", "config", "prefix", "rbac", "render", "tags")

__version__ = "0.0.0"
# Note: Do not import submodules with runtime side effects here.
# CoreOps must be importable without environment variables present.


def __getattr__(name: str) -> ModuleType:
    """Lazily import submodules on attribute access."""

    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> Iterable[str]:
    """Return available attributes for auto-completion tools."""

    return sorted({*globals().keys(), *__all__})


__docformat__ = "restructuredtext"
