"""CoreOps helpers packaged for internal reuse."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Dict, Iterable

__all__ = (
    "cog",
    "config",
    "prefix",
    "rbac",
    "render",
    "tags",
    "helpers",
    "help",
    "cronlog",
    "cron_summary",
    "commands",
    "ops",
    "cache_public",
)

__version__ = "0.0.0"
# Note: Do not import submodules with runtime side effects here.
# CoreOps must be importable without environment variables present.

# Re-export table generated from in-repo usages of ``from c1c_coreops import ...``.
# No current symbols require re-exporting beyond the modules in ``__all__``.
__exports__: Dict[str, str] = {}


def __getattr__(name: str) -> ModuleType | object:
    """Lazily import submodules and selected symbols on attribute access."""

    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module

    owner = __exports__.get(name)
    if owner:
        module = importlib.import_module(f".{owner}", __name__)
        obj = getattr(module, name)
        globals()[name] = obj
        return obj

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> Iterable[str]:
    """Return available attributes for auto-completion tools."""

    return sorted({*globals().keys(), *__all__, *__exports__.keys()})


__docformat__ = "restructuredtext"
