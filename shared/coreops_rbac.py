"""Legacy shim forwarding RBAC helpers to the new package."""

import logging as _logging

_once = getattr(_logging, "_c1c_coreops_shim_once", set())
if __name__ not in _once:
    _logging.getLogger("c1c.migration").warning(
        f"[deprecate] {__name__} → c1c_coreops.{__name__.split('.')[-1]} (will be removed next release)"
    )
    _once.add(__name__)
    setattr(_logging, "_c1c_coreops_shim_once", _once)

from c1c_coreops.rbac import *  # noqa: F401,F403
