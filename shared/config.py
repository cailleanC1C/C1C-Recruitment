"""Runtime configuration helpers for the unified bot."""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, Iterable, Optional, Sequence, Set

from config import runtime as _runtime
from shared.redaction import mask_secret, mask_service_account, sanitize_text

__all__ = [
    "reload_config",
    "get_config_snapshot",
    "get_port",
    "get_env_name",
    "get_bot_name",
    "get_watchdog_check_sec",
    "get_watchdog_stall_sec",
    "get_watchdog_disconnect_grace_sec",
    "get_command_prefix",
    "get_discord_token",
    "get_allowed_guild_ids",
    "is_guild_allowed",
    "get_log_channel_id",
    "get_notify_channel_id",
    "get_notify_ping_role_id",
    "get_recruiters_thread_id",
    "get_welcome_general_channel_id",
    "get_welcome_channel_id",
    "get_promo_channel_id",
    "get_refresh_times",
    "get_refresh_timezone",
    "get_gspread_credentials",
    "get_recruitment_sheet_id",
    "get_onboarding_sheet_id",
    "get_admin_role_ids",
    "get_staff_role_ids",
    "get_recruiter_role_ids",
    "get_lead_role_ids",
    "get_welcome_enabled",
    "get_enable_welcome_watcher",
    "get_enable_promo_watcher",
    "get_enable_notify_fallback",
    "get_strict_probe",
    "get_search_results_soft_cap",
    "get_clan_tags_cache_ttl_sec",
    "get_cleanup_age_hours",
    "get_panel_thread_mode",
    "get_panel_fixed_thread_id",
    "get_public_base_url",
    "get_render_external_url",
    "get_emoji_max_bytes",
    "get_emoji_pad_size",
    "get_emoji_pad_box",
    "get_tag_badge_px",
    "get_tag_badge_box",
    "get_strict_emoji_proxy",
    "redact_token",
    "redact_ids",
    "redact_value",
]

log = logging.getLogger("c1c.config")

_SECRET_VALUE = "set"
_MISSING_VALUE = "—"
_DEFAULT_LOG_CHANNEL_ID = 1415330837968191629  # #bot-production
_INT_RE = re.compile(r"\d+")

_CONFIG: Dict[str, object] = {}

_SECRET_KEYS = {
    "DISCORD_TOKEN",
    "GSPREAD_CREDENTIALS",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
}


def _redact_value(key: str, value: object) -> str:
    """Best-effort redaction for import-time logging."""

    key_upper = str(key).upper()

    if (
        key_upper in _SECRET_KEYS
        or "TOKEN" in key_upper
        or "CREDENTIAL" in key_upper
        or "SERVICE_ACCOUNT" in key_upper
        or key_upper.endswith("_SECRET")
    ):
        if value in (None, "", [], (), {}):
            return _MISSING_VALUE
        text = str(value)
        stripped = text.strip()
        if not stripped:
            return _MISSING_VALUE
        masked = sanitize_text(text)
        if isinstance(masked, str) and masked != text:
            return masked
        if "service_account" in stripped and "private_key" in stripped:
            return mask_service_account(stripped)
        return mask_secret(stripped)

    if value in (None, "", [], (), {}):
        return _MISSING_VALUE

    redacted = sanitize_text(value)
    return str(redacted)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _first_int(raw: str | None) -> Optional[int]:
    if not raw:
        return None
    for match in _INT_RE.finditer(raw):
        try:
            return int(match.group(0))
        except (TypeError, ValueError):
            continue
    return None


def _int_set(raw: str | None) -> Set[int]:
    values: Set[int] = set()
    if not raw:
        return values
    for match in _INT_RE.finditer(raw):
        try:
            values.add(int(match.group(0)))
        except (TypeError, ValueError):
            continue
    return values


def _parse_schedule(raw: str | None, default: Sequence[str]) -> list[str]:
    parts = []
    if raw:
        for chunk in raw.split(","):
            item = chunk.strip()
            if item:
                parts.append(item)
    if parts:
        return parts
    return [str(item).strip() for item in default if str(item).strip()]


def _int_env(
    key: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Parse an optional integer environment variable defensively."""

    raw = os.getenv(key)
    if raw is None:
        return default

    text = str(raw).strip()
    if not text:
        return default

    try:
        value = int(text)
    except Exception:  # pragma: no cover - defensive logging path
        logging.warning("config: %s='%s' invalid; using default %s", key, text, default)
        return default

    if min_value is not None and value < min_value:
        logging.warning("config: %s=%s < min %s; clamping", key, value, min_value)
        value = min_value

    if max_value is not None and value > max_value:
        logging.warning("config: %s=%s > max %s; clamping", key, value, max_value)
        value = max_value

    return value


def _float_env(
    key: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Parse an optional float environment variable defensively."""

    raw = os.getenv(key)
    if raw is None:
        return default

    text = str(raw).strip()
    if not text:
        return default

    try:
        value = float(text)
    except Exception:  # pragma: no cover - defensive logging path
        logging.warning("config: %s='%s' invalid; using default %s", key, text, default)
        return default

    if min_value is not None and value < min_value:
        logging.warning("config: %s=%s < min %s; clamping", key, value, min_value)
        value = min_value

    if max_value is not None and value > max_value:
        logging.warning("config: %s=%s > max %s; clamping", key, value, max_value)
        value = max_value

    return value


def _log_snapshot(snapshot: Dict[str, object]) -> None:
    redacted = {key: _redact_value(key, value) for key, value in snapshot.items()}
    log.info("config loaded", extra={"config": redacted})


def _load_config() -> Dict[str, object]:
    keepalive = _runtime.get_watchdog_check_sec()
    stall = _runtime.get_watchdog_stall_sec()
    grace = _runtime.get_watchdog_disconnect_grace_sec(stall)

    log_channel_env = _first_int(os.getenv("LOG_CHANNEL_ID"))
    log_channel = log_channel_env or _DEFAULT_LOG_CHANNEL_ID

    refresh_default = ("02:00", "10:00", "18:00")

    config: Dict[str, object] = {
        "PORT": _runtime.get_port(),
        "BOT_NAME": _runtime.get_bot_name(),
        "COMMAND_PREFIX": _runtime.get_command_prefix(),
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN", ""),
        "ENV_NAME": _runtime.get_env_name(),
        "GUILD_IDS": _int_set(os.getenv("GUILD_IDS")),
        "TIMEZONE": (os.getenv("TIMEZONE") or "Europe/Vienna").strip() or "Europe/Vienna",
        "REFRESH_TIMES": _parse_schedule(os.getenv("REFRESH_TIMES"), refresh_default),
        "GSPREAD_CREDENTIALS": os.getenv("GSPREAD_CREDENTIALS", ""),
        "RECRUITMENT_SHEET_ID": (os.getenv("RECRUITMENT_SHEET_ID") or "").strip(),
        "ONBOARDING_SHEET_ID": (os.getenv("ONBOARDING_SHEET_ID") or "").strip(),
        "ADMIN_ROLE_IDS": _int_set(os.getenv("ADMIN_ROLE_IDS")),
        "STAFF_ROLE_IDS": _int_set(os.getenv("STAFF_ROLE_IDS")),
        "RECRUITER_ROLE_IDS": _int_set(os.getenv("RECRUITER_ROLE_IDS")),
        "LEAD_ROLE_IDS": _int_set(os.getenv("LEAD_ROLE_IDS")),
        "RECRUITERS_THREAD_ID": _first_int(os.getenv("RECRUITERS_THREAD_ID")),
        "WELCOME_GENERAL_CHANNEL_ID": _first_int(os.getenv("WELCOME_GENERAL_CHANNEL_ID")),
        "WELCOME_CHANNEL_ID": _first_int(os.getenv("WELCOME_CHANNEL_ID")),
        "PROMO_CHANNEL_ID": _first_int(os.getenv("PROMO_CHANNEL_ID")),
        "LOG_CHANNEL_ID": int(log_channel),
        "NOTIFY_CHANNEL_ID": _first_int(os.getenv("NOTIFY_CHANNEL_ID")),
        "NOTIFY_PING_ROLE_ID": _first_int(os.getenv("NOTIFY_PING_ROLE_ID")),
        "WELCOME_ENABLED": _env_bool("WELCOME_ENABLED", True),
        "ENABLE_WELCOME_WATCHER": _env_bool("ENABLE_WELCOME_WATCHER", True),
        "ENABLE_PROMO_WATCHER": _env_bool("ENABLE_PROMO_WATCHER", True),
        "ENABLE_NOTIFY_FALLBACK": _env_bool("ENABLE_NOTIFY_FALLBACK", True),
        "STRICT_PROBE": _env_bool("STRICT_PROBE", False),
        "SEARCH_RESULTS_SOFT_CAP": _int_env("SEARCH_RESULTS_SOFT_CAP", 25, min_value=1),
        "WATCHDOG_CHECK_SEC": keepalive,
        "WATCHDOG_STALL_SEC": stall,
        "WATCHDOG_DISCONNECT_GRACE_SEC": grace,
        "CLAN_TAGS_CACHE_TTL_SEC": _int_env("CLAN_TAGS_CACHE_TTL_SEC", 3600, min_value=60),
        "CLEANUP_AGE_HOURS": _int_env("CLEANUP_AGE_HOURS", 72, min_value=1),
        "PANEL_THREAD_MODE": (os.getenv("PANEL_THREAD_MODE") or "same").strip().lower() or "same",
        "PANEL_FIXED_THREAD_ID": _first_int(os.getenv("PANEL_FIXED_THREAD_ID")),
        "BOT_VERSION": os.getenv("BOT_VERSION", "dev"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "PUBLIC_BASE_URL": (os.getenv("PUBLIC_BASE_URL") or "").strip(),
        "RENDER_EXTERNAL_URL": (os.getenv("RENDER_EXTERNAL_URL") or "").strip(),
        "EMOJI_MAX_BYTES": _int_env("EMOJI_MAX_BYTES", 2_000_000, min_value=1),
        "EMOJI_PAD_SIZE": _int_env("EMOJI_PAD_SIZE", 256, min_value=64, max_value=512),
        "EMOJI_PAD_BOX": _float_env("EMOJI_PAD_BOX", 0.85, min_value=0.2, max_value=0.95),
        "TAG_BADGE_PX": _int_env("TAG_BADGE_PX", 128, min_value=32, max_value=512),
        "TAG_BADGE_BOX": _float_env("TAG_BADGE_BOX", 0.90, min_value=0.2, max_value=0.95),
        "STRICT_EMOJI_PROXY": _env_bool("STRICT_EMOJI_PROXY", True),
    }

    return config


def reload_config() -> Dict[str, object]:
    """Reload configuration from environment and return a snapshot."""

    global _CONFIG
    snapshot = _load_config()
    _CONFIG = snapshot
    _log_snapshot(snapshot)
    return dict(_CONFIG)


reload_config()


def get_config_snapshot() -> Dict[str, object]:
    """Return a shallow copy of the cached config values."""

    return dict(_CONFIG)


def get_port(default: int = 10000) -> int:
    try:
        return int(_CONFIG.get("PORT", default))
    except (TypeError, ValueError):
        return default


def get_env_name(default: str = "dev") -> str:
    value = _CONFIG.get("ENV_NAME")
    return str(value) if isinstance(value, str) and value else default


def get_bot_name(default: str = "C1C-Recruitment") -> str:
    value = _CONFIG.get("BOT_NAME")
    return str(value) if isinstance(value, str) and value else default


def get_watchdog_check_sec(default_prod: int = 360, default_nonprod: int = 60) -> int:
    fallback = _runtime.get_watchdog_check_sec(default_prod, default_nonprod)
    try:
        return int(_CONFIG.get("WATCHDOG_CHECK_SEC", fallback))
    except (TypeError, ValueError):
        return fallback


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


def get_command_prefix(default: str = "!") -> str:
    return "!"


def get_discord_token() -> str:
    token = _CONFIG.get("DISCORD_TOKEN", "")
    return str(token)


def get_allowed_guild_ids() -> Set[int]:
    raw = _CONFIG.get("GUILD_IDS", set())
    if isinstance(raw, set):
        return set(raw)
    if isinstance(raw, (list, tuple)):
        result: Set[int] = set()
        for value in raw:
            try:
                result.add(int(value))
            except (TypeError, ValueError):
                continue
        return result
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


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_id(key: str) -> Optional[int]:
    value = _CONFIG.get(key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def get_log_channel_id() -> int:
    return _coerce_int(_CONFIG.get("LOG_CHANNEL_ID"), _DEFAULT_LOG_CHANNEL_ID)


def get_notify_channel_id() -> Optional[int]:
    return _optional_id("NOTIFY_CHANNEL_ID")


def get_notify_ping_role_id() -> Optional[int]:
    return _optional_id("NOTIFY_PING_ROLE_ID")


def get_recruiters_thread_id() -> Optional[int]:
    return _optional_id("RECRUITERS_THREAD_ID")


def get_welcome_general_channel_id() -> Optional[int]:
    return _optional_id("WELCOME_GENERAL_CHANNEL_ID")


def get_welcome_channel_id() -> Optional[int]:
    return _optional_id("WELCOME_CHANNEL_ID")


def get_promo_channel_id() -> Optional[int]:
    return _optional_id("PROMO_CHANNEL_ID")


def get_refresh_times(default: Iterable[str] = ("02:00", "10:00", "18:00")) -> list[str]:
    raw = _CONFIG.get("REFRESH_TIMES")
    if isinstance(raw, (list, tuple, set)):
        values = [str(part).strip() for part in raw if str(part).strip()]
        if values:
            return values
    return [str(x).strip() for x in default if str(x).strip()]


def get_refresh_timezone(default: str = "Europe/Vienna") -> str:
    raw = _CONFIG.get("TIMEZONE")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def get_gspread_credentials() -> str:
    value = _CONFIG.get("GSPREAD_CREDENTIALS", "")
    return str(value)


def get_recruitment_sheet_id() -> str:
    return str(_CONFIG.get("RECRUITMENT_SHEET_ID", ""))


def get_onboarding_sheet_id() -> str:
    return str(_CONFIG.get("ONBOARDING_SHEET_ID", ""))


def _role_set(key: str) -> Set[int]:
    raw = _CONFIG.get(key, set())
    if isinstance(raw, set):
        return set(raw)
    if isinstance(raw, (list, tuple)):
        result: Set[int] = set()
        for value in raw:
            try:
                result.add(int(value))
            except (TypeError, ValueError):
                continue
        return result
    return set()


def get_admin_role_ids() -> Set[int]:
    return _role_set("ADMIN_ROLE_IDS")


def get_staff_role_ids() -> Set[int]:
    return _role_set("STAFF_ROLE_IDS")


def get_recruiter_role_ids() -> Set[int]:
    return _role_set("RECRUITER_ROLE_IDS")


def get_lead_role_ids() -> Set[int]:
    return _role_set("LEAD_ROLE_IDS")


def get_welcome_enabled() -> bool:
    return bool(_CONFIG.get("WELCOME_ENABLED", True))


def get_enable_welcome_watcher() -> bool:
    return bool(_CONFIG.get("ENABLE_WELCOME_WATCHER", True))


def get_enable_promo_watcher() -> bool:
    return bool(_CONFIG.get("ENABLE_PROMO_WATCHER", True))


def get_enable_notify_fallback() -> bool:
    return bool(_CONFIG.get("ENABLE_NOTIFY_FALLBACK", True))


def get_strict_probe() -> bool:
    return bool(_CONFIG.get("STRICT_PROBE", False))


def get_search_results_soft_cap(default: int = 25) -> int:
    value = _CONFIG.get("SEARCH_RESULTS_SOFT_CAP", default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_clan_tags_cache_ttl_sec(default: int = 3600) -> int:
    value = _CONFIG.get("CLAN_TAGS_CACHE_TTL_SEC", default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_cleanup_age_hours(default: int = 72) -> int:
    value = _CONFIG.get("CLEANUP_AGE_HOURS", default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_panel_thread_mode(default: str = "same") -> str:
    value = _CONFIG.get("PANEL_THREAD_MODE", default)
    text = str(value).strip().lower()
    return text or default


def get_panel_fixed_thread_id() -> Optional[int]:
    return _optional_id("PANEL_FIXED_THREAD_ID")


def get_public_base_url() -> str | None:
    value = _CONFIG.get("PUBLIC_BASE_URL")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def get_render_external_url() -> str | None:
    value = _CONFIG.get("RENDER_EXTERNAL_URL")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def get_emoji_max_bytes(default: int = 2_000_000) -> int:
    value = _CONFIG.get("EMOJI_MAX_BYTES", default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def get_emoji_pad_size(default: int = 256) -> int:
    value = _CONFIG.get("EMOJI_PAD_SIZE", default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(64, min(512, parsed))


def get_emoji_pad_box(default: float = 0.85) -> float:
    value = _CONFIG.get("EMOJI_PAD_BOX", default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.2, min(0.95, parsed))


def get_tag_badge_px(default: int = 128) -> int:
    value = _CONFIG.get("TAG_BADGE_PX", default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(32, min(512, parsed))


def get_tag_badge_box(default: float = 0.9) -> float:
    value = _CONFIG.get("TAG_BADGE_BOX", default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.2, min(0.95, parsed))


def get_strict_emoji_proxy(default: bool = True) -> bool:
    value = _CONFIG.get("STRICT_EMOJI_PROXY")
    if isinstance(value, bool):
        return value
    return default


def redact_token(token: Optional[str]) -> str:
    token = (token or "").strip()
    if not token:
        return _MISSING_VALUE
    masked = sanitize_text(token)
    if isinstance(masked, str) and masked != token:
        return masked
    return mask_secret(token)


def redact_ids(values: Iterable[int]) -> str:
    uniq = sorted({int(v) for v in values if isinstance(v, int)})
    if not uniq:
        return _MISSING_VALUE
    if len(uniq) <= 3:
        return ", ".join(str(v) for v in uniq)
    return f"{len(uniq)} ids"


def redact_value(key: str, value: object) -> str:
    key_upper = str(key).upper()

    if (
        key_upper in _SECRET_KEYS
        or "TOKEN" in key_upper
        or "CREDENTIAL" in key_upper
        or "SERVICE_ACCOUNT" in key_upper
        or key_upper.endswith("_SECRET")
    ):
        return _redact_value(key, value)

    if key_upper in {
        "ADMIN_IDS",
        "ADMIN_ROLE_IDS",
        "STAFF_ROLE_IDS",
        "RECRUITER_ROLE_IDS",
        "LEAD_ROLE_IDS",
        "GUILD_IDS",
    }:
        try:
            iterable = list(value)  # type: ignore[arg-type]
        except TypeError:
            iterable = []
        return redact_ids(int(v) for v in iterable if isinstance(v, int))

    return _redact_value(key, value)
