"""Runtime configuration helpers for the unified bot."""

from __future__ import annotations

from typing import Iterable, List, Optional

from config import runtime as _runtime

__all__ = [
    "get_port",
    "get_env_name",
    "get_bot_name",
    "get_keepalive_interval_sec",
    "get_watchdog_stall_sec",
    "get_watchdog_disconnect_grace_sec",
    "get_command_prefix",
    "get_admin_role_id",
    "get_staff_role_ids",
    "get_admin_ids",
]


def get_port(default: int = 10000) -> int:
    return _runtime.get_port(default)


def get_env_name(default: str = "dev") -> str:
    return _runtime.get_env_name(default)


def get_bot_name(default: str = "C1C-Recruitment") -> str:
    return _runtime.get_bot_name(default)


def get_keepalive_interval_sec(
    default_prod: int = 360,
    default_nonprod: int = 60,
) -> int:
    return _runtime.get_keepalive_interval_sec(default_prod, default_nonprod)


def get_watchdog_stall_sec(default: Optional[int] = None) -> int:
    return _runtime.get_watchdog_stall_sec(default)


def get_watchdog_disconnect_grace_sec(default: Optional[int] = None) -> int:
    return _runtime.get_watchdog_disconnect_grace_sec(default)


def get_command_prefix(default: str = "rec") -> str:
    return _runtime.get_command_prefix(default)


def get_admin_role_id() -> Optional[int]:
    try:
        from shared.coreops_rbac import get_admin_role_id as _get
    except Exception:
        return None
    return _get()


def get_staff_role_ids() -> Iterable[int]:
    try:
        from shared.coreops_rbac import get_staff_role_ids as _get
    except Exception:
        return []
    return _get()


def get_admin_ids() -> List[int]:
    return _runtime.get_admin_ids()
