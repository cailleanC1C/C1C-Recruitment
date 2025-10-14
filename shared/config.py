"""Shared configuration loader for recruitment bot modules."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Tuple

from config.runtime import (
    get_command_prefix,
    get_env_name,
    get_keepalive_interval_sec,
    get_watchdog_disconnect_grace_sec,
    get_watchdog_stall_sec,
)

# Channel where production logs land when env override absent (#bot-production).
_DEFAULT_LOG_CHANNEL_ID = 1415330837968191629
_DEFAULT_TABS = ("coreops",)

_TOKEN_SPLIT_RE = re.compile(r"[,\s]+")


def _split_tokens(raw: str | None) -> Iterable[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    return (tok for tok in _TOKEN_SPLIT_RE.split(raw) if tok)


def _parse_int(tok: str) -> int | None:
    try:
        return int(tok)
    except (TypeError, ValueError):
        digits = re.search(r"\d+", tok)
        if digits is None:
            return None
        try:
            return int(digits.group(0))
        except (TypeError, ValueError):
            return None


def _unique(seq: Iterable[Tuple[str, int | str]]) -> list:
    seen = set()
    out = []
    for key, value in seq:
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _parse_int_list(raw: str | None) -> Tuple[int, ...]:
    values = []
    for tok in _split_tokens(raw):
        parsed = _parse_int(tok)
        if parsed is not None:
            values.append(parsed)
    # preserve order but drop duplicates
    deduped = _unique((str(v), v) for v in values)
    return tuple(int(v) for v in deduped)


def _parse_str_list(raw: str | None) -> Tuple[str, ...]:
    tokens = []
    for tok in _split_tokens(raw):
        cleaned = tok.strip()
        if cleaned:
            tokens.append(cleaned.lower())
    deduped = _unique(((tok.lower(), tok) for tok in tokens))
    return tuple(str(v) for v in deduped)


def _int_or_none(value: str | None, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    parsed = _parse_int(value)
    if parsed is None:
        return default
    return parsed


@dataclass(frozen=True)
class SharedConfig:
    env_name: str
    bot_name: str
    bot_version: str
    command_prefix: str
    discord_token: str | None
    admin_role_id: int | None
    staff_role_ids: Tuple[int, ...]
    guild_ids: Tuple[int, ...]
    enabled_tabs: Tuple[str, ...]
    log_channel_id: int | None
    keepalive_interval_sec: int
    watchdog_stall_sec: int
    watchdog_disconnect_grace_sec: int


@lru_cache(maxsize=1)
def get_shared_config() -> SharedConfig:
    env_name = get_env_name().strip() or "dev"
    bot_name = (os.getenv("BOT_NAME") or "C1C Recruitment").strip() or "C1C Recruitment"
    bot_version = (os.getenv("BOT_VERSION") or "dev").strip() or "dev"
    command_prefix = get_command_prefix().strip() or "rec"

    admin_role_id = _int_or_none(os.getenv("ADMIN_ROLE_ID"))
    staff_role_ids = _parse_int_list(os.getenv("STAFF_ROLE_IDS"))

    guild_ids = _parse_int_list(os.getenv("GUILD_IDS"))

    enabled_tabs = _parse_str_list(os.getenv("ENABLED_TABS"))
    if not enabled_tabs:
        enabled_tabs = _DEFAULT_TABS

    log_channel_raw = os.getenv("LOG_CHANNEL_ID")
    if log_channel_raw is None:
        log_channel_id = _DEFAULT_LOG_CHANNEL_ID
    else:
        log_channel_id = _int_or_none(log_channel_raw, default=_DEFAULT_LOG_CHANNEL_ID)
    if log_channel_id in {None, 0}:
        log_channel_id = None

    keepalive_interval_sec = get_keepalive_interval_sec()
    watchdog_stall_sec = get_watchdog_stall_sec()
    watchdog_disconnect_grace_sec = get_watchdog_disconnect_grace_sec(watchdog_stall_sec)

    discord_token = (os.getenv("DISCORD_TOKEN") or "").strip() or None

    return SharedConfig(
        env_name=env_name,
        bot_name=bot_name,
        bot_version=bot_version,
        command_prefix=command_prefix,
        discord_token=discord_token,
        admin_role_id=admin_role_id,
        staff_role_ids=staff_role_ids,
        guild_ids=guild_ids,
        enabled_tabs=enabled_tabs,
        log_channel_id=log_channel_id,
        keepalive_interval_sec=keepalive_interval_sec,
        watchdog_stall_sec=watchdog_stall_sec,
        watchdog_disconnect_grace_sec=watchdog_disconnect_grace_sec,
    )


def redact_secret(value: str | None) -> str:
    if not value:
        return "unset"
    if len(value) <= 4:
        return "••••"
    return f"{value[:4]}…{value[-2:]}"


def redacted_items(cfg: SharedConfig | None = None) -> dict[str, object]:
    cfg = cfg or get_shared_config()
    return {
        "ENV_NAME": cfg.env_name,
        "BOT_NAME": cfg.bot_name,
        "BOT_VERSION": cfg.bot_version,
        "COMMAND_PREFIX": cfg.command_prefix,
        "ADMIN_ROLE_ID": cfg.admin_role_id or "unset",
        "STAFF_ROLE_IDS": list(cfg.staff_role_ids),
        "GUILD_IDS": list(cfg.guild_ids),
        "ENABLED_TABS": list(cfg.enabled_tabs),
        "LOG_CHANNEL_ID": cfg.log_channel_id,
        "KEEPALIVE_INTERVAL_SEC": cfg.keepalive_interval_sec,
        "WATCHDOG_STALL_SEC": cfg.watchdog_stall_sec,
        "WATCHDOG_DISCONNECT_GRACE_SEC": cfg.watchdog_disconnect_grace_sec,
        "DISCORD_TOKEN": redact_secret(cfg.discord_token),
    }


__all__ = ["SharedConfig", "get_shared_config", "redact_secret", "redacted_items"]
