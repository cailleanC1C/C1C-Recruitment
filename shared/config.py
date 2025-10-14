"""Runtime configuration helpers for the unified bot."""

from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional, Set

from config import runtime as _runtime

__all__ = [
    "reload_config",
    "get_config_snapshot",
    "get_port",
    "get_env_name",
    "get_bot_name",
    "get_keepalive_interval_sec",
    "get_watchdog_stall_sec",
    "get_watchdog_disconnect_grace_sec",
    "get_command_prefix",
    "get_admin_ids",
    "get_admin_role_ids",
    "get_staff_role_ids",
    "get_allowed_guild_ids",
    "is_guild_allowed",
    "get_log_channel_id",
    "get_sheet_tab_names",
    "get_google_sheet_id",
    "redact_token",
    "redact_ids",
    "redact_value",
]

_DEFAULT_LOG_CHANNEL_ID = 1415330837968191629  # #bot-production
_DEFAULT_SHEET_CONFIG_TAB = "Config"
_DEFAULT_WORKSHEET_NAME = "bot_info"
_DEFAULT_WELCOME_TEMPLATES_TAB = "WelcomeTemplates"
_SECRET_VALUE = "set"
_MISSING_VALUE = "—"
_INT_RE = re.compile(r"\d+")


# Cache populated on import; reload() is exposed for tests/introspection.
_CONFIG: Dict[str, object] = {}


def _coerce_int(raw: Optional[str], default: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return value


def _first_int(raw: str) -> Optional[int]:
    for match in _INT_RE.finditer(raw or ""):
        try:
            return int(match.group(0))
        except (TypeError, ValueError):
            continue
    return None


def _int_set(raw: str) -> Set[int]:
    values: Set[int] = set()
    for match in _INT_RE.finditer(raw or ""):
        try:
            values.add(int(match.group(0)))
        except (TypeError, ValueError):
            continue
    return values


def _load_config() -> Dict[str, object]:
    keepalive = _runtime.get_keepalive_interval_sec()
    stall = _runtime.get_watchdog_stall_sec()
    disconnect_grace = _runtime.get_watchdog_disconnect_grace_sec(stall)

    admin_roles = _int_set(os.getenv("ADMIN_ROLE_IDS", ""))
    staff_roles = _int_set(os.getenv("STAFF_ROLE_IDS", ""))
    guild_ids = _int_set(os.getenv("GUILD_IDS", ""))
    log_channel_env = _first_int(os.getenv("LOG_CHANNEL_ID", ""))
    log_channel = log_channel_env if log_channel_env else _DEFAULT_LOG_CHANNEL_ID

    sheet_config_tab = os.getenv("SHEET_CONFIG_TAB", _DEFAULT_SHEET_CONFIG_TAB)
    worksheet_name = os.getenv("WORKSHEET_NAME", _DEFAULT_WORKSHEET_NAME)
    welcome_tab = (
        os.getenv("WELCOME_TEMPLATES_TAB")
        or os.getenv("WELCOME_SHEET_TAB")
        or _DEFAULT_WELCOME_TEMPLATES_TAB
    )

    google_sheet_id = os.getenv("GOOGLE_SHEET_ID") or os.getenv("GSHEET_ID") or ""
    sheets_cache_ttl = _coerce_int(os.getenv("SHEETS_CACHE_TTL_SEC"), 900)

    return {
        "PORT": _runtime.get_port(),
        "ENV_NAME": _runtime.get_env_name(),
        "BOT_NAME": _runtime.get_bot_name(),
        "COMMAND_PREFIX": _runtime.get_command_prefix(),
        "KEEPALIVE_INTERVAL_SEC": keepalive,
        "WATCHDOG_STALL_SEC": stall,
        "WATCHDOG_DISCONNECT_GRACE_SEC": disconnect_grace,
        "ADMIN_IDS": _runtime.get_admin_ids(),
        "ADMIN_ROLE_IDS": admin_roles,
        "STAFF_ROLE_IDS": staff_roles,
        "GUILD_IDS": guild_ids,
        "LOG_CHANNEL_ID": log_channel,
        "LOG_CHANNEL_OVERRIDDEN": bool(log_channel_env),
        "SHEET_CONFIG_TAB": sheet_config_tab,
        "WORKSHEET_NAME": worksheet_name,
        "WELCOME_TEMPLATES_TAB": welcome_tab,
        "GOOGLE_SHEET_ID": google_sheet_id,
        "SHEETS_CACHE_TTL_SEC": sheets_cache_ttl,
        "BOT_VERSION": os.getenv("BOT_VERSION", "dev"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "DISCORD_TOKEN_SET": bool(os.getenv("DISCORD_TOKEN")),
        "GOOGLE_SERVICE_ACCOUNT_JSON_SET": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "GSPREAD_CREDENTIALS_SET": bool(os.getenv("GSPREAD_CREDENTIALS")),
    }


def reload_config() -> Dict[str, object]:
    """Reload configuration from environment and return a snapshot."""

    global _CONFIG
    _CONFIG = _load_config()
    return dict(_CONFIG)


# Populate cache on import.
reload_config()


def get_config_snapshot() -> Dict[str, object]:
    """Return a shallow copy of the cached config values."""

    return dict(_CONFIG)


def get_port(default: int = 10000) -> int:
    return int(_CONFIG.get("PORT", default))


def get_env_name(default: str = "dev") -> str:
    value = _CONFIG.get("ENV_NAME")
    return str(value) if isinstance(value, str) and value else default


def get_bot_name(default: str = "C1C-Recruitment") -> str:
    value = _CONFIG.get("BOT_NAME")
    return str(value) if isinstance(value, str) and value else default


def get_keepalive_interval_sec(
    default_prod: int = 360, default_nonprod: int = 60
) -> int:
    fallback = _runtime.get_keepalive_interval_sec(default_prod, default_nonprod)
    return int(_CONFIG.get("KEEPALIVE_INTERVAL_SEC", fallback))


def get_watchdog_stall_sec(default: Optional[int] = None) -> int:
    value = _CONFIG.get("WATCHDOG_STALL_SEC")
    if isinstance(value, int):
        return value
    if default is not None:
        return default
    return _runtime.get_watchdog_stall_sec(default)


def get_watchdog_disconnect_grace_sec(default: Optional[int] = None) -> int:
    value = _CONFIG.get("WATCHDOG_DISCONNECT_GRACE_SEC")
    if isinstance(value, int):
        return value
    if default is not None:
        return default
    return _runtime.get_watchdog_disconnect_grace_sec(default)


def get_command_prefix(default: str = "rec") -> str:
    value = _CONFIG.get("COMMAND_PREFIX")
    return str(value) if isinstance(value, str) and value else default


def get_admin_ids() -> List[int]:
    raw = _CONFIG.get("ADMIN_IDS", [])
    return list(raw) if isinstance(raw, list) else []


def get_admin_role_ids() -> Set[int]:
    from shared.coreops_rbac import get_admin_role_ids as _get

    try:
        return set(_get())
    except Exception:
        return set()


def get_staff_role_ids() -> Set[int]:
    from shared.coreops_rbac import get_staff_role_ids as _get

    try:
        return set(_get())
    except Exception:
        return set()


def get_allowed_guild_ids() -> Set[int]:
    raw = _CONFIG.get("GUILD_IDS", set())
    if isinstance(raw, set):
        return set(raw)
    if isinstance(raw, (list, tuple)):
        return {int(x) for x in raw if isinstance(x, int)}
    return set()


def is_guild_allowed(guild_id: int) -> bool:
    allowed = get_allowed_guild_ids()
    if not allowed:
        return True
    try:
        value = int(guild_id)
    except (TypeError, ValueError):
        return False
    return value in allowed


def get_log_channel_id() -> int:
    value = _CONFIG.get("LOG_CHANNEL_ID", _DEFAULT_LOG_CHANNEL_ID)
    try:
        return int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LOG_CHANNEL_ID


def get_sheet_tab_names() -> Dict[str, str]:
    return {
        "worksheet": str(_CONFIG.get("WORKSHEET_NAME", _DEFAULT_WORKSHEET_NAME)),
        "config": str(_CONFIG.get("SHEET_CONFIG_TAB", _DEFAULT_SHEET_CONFIG_TAB)),
        "welcome_templates": str(
            _CONFIG.get("WELCOME_TEMPLATES_TAB", _DEFAULT_WELCOME_TEMPLATES_TAB)
        ),
    }


def get_google_sheet_id() -> str:
    return str(_CONFIG.get("GOOGLE_SHEET_ID", ""))


def redact_token(token: Optional[str]) -> str:
    token = (token or "").strip()
    if not token:
        return _MISSING_VALUE
    if len(token) <= 8:
        return "••••"
    return f"{token[:4]}…{token[-4:]}"


def redact_ids(values: Iterable[int]) -> str:
    uniq = sorted({int(v) for v in values if isinstance(v, int)})
    if not uniq:
        return _MISSING_VALUE
    if len(uniq) <= 3:
        return ", ".join(str(v) for v in uniq)
    return f"{len(uniq)} ids"


def redact_value(key: str, value: object) -> str:
    key = key.upper()
    if key in {"DISCORD_TOKEN", "TOKEN"}:
        return redact_token(str(value) if value is not None else "")
    if key in {"GOOGLE_SERVICE_ACCOUNT_JSON", "GSPREAD_CREDENTIALS"}:
        return _SECRET_VALUE if value else _MISSING_VALUE
    if key in {"ADMIN_IDS", "ADMIN_ROLE_IDS", "STAFF_ROLE_IDS", "GUILD_IDS"}:
        try:
            iterable = list(value)  # type: ignore[arg-type]
        except TypeError:
            iterable = []
        return redact_ids(int(v) for v in iterable if isinstance(v, int))
    if value in (None, "", [], (), {}):
        return _MISSING_VALUE
    return str(value)
