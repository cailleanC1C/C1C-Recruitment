"""Helpers for working with Google Sheets (import side-effect free)."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "get_service_account_client",
    "onboarding",
    "onboarding_questions",
    "open_by_key",
    "register_default_cache_buckets",
    "recruitment",
]

_LAZY_MODULES = {
    "onboarding": "shared.sheets.onboarding",
    "onboarding_questions": "shared.sheets.onboarding_questions",
    "recruitment": "shared.sheets.recruitment",
}

_LAZY_ATTRS = {
    "get_service_account_client": ("shared.sheets.core", "get_service_account_client"),
    "open_by_key": ("shared.sheets.core", "open_by_key"),
    "register_default_cache_buckets": (
        "shared.sheets.runtime",
        "register_default_cache_buckets",
    ),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MODULES:
        module = importlib.import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = importlib.import_module(module_name)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module 'shared.sheets' has no attribute {name!r}")


def __dir__() -> list[str]:
    exported = {name for name in globals() if not name.startswith("_")}
    exported.update(__all__)
    return sorted(exported)
