"""CoreOps helpers packaged for internal reuse."""

from . import cog as _cog
from . import config as _config
from . import prefix as _prefix
from . import rbac as _rbac
from . import render as _render
from . import tags as _tags

from .cog import *  # noqa: F401,F403
from .config import *  # noqa: F401,F403
from .prefix import *  # noqa: F401,F403
from .rbac import *  # noqa: F401,F403
from .render import *  # noqa: F401,F403
from .tags import *  # noqa: F401,F403

__all__: list[str] = []
_seen: set[str] = set()
for _module in (_cog, _config, _rbac, _render, _prefix, _tags):
    names = getattr(_module, "__all__", None)
    if names is None:
        names = [name for name in vars(_module) if not name.startswith("_")]
    for name in names:
        if name in _seen:
            continue
        _seen.add(name)
        __all__.append(name)

__all__ = tuple(__all__)

__docformat__ = "restructuredtext"

