from __future__ import annotations

# config/runtime.py
import os
from typing import Iterable, List


def get_port(default: int = 10000) -> int:
    """
    Returns the port for the aiohttp health server.
    Render provides $PORT; locally we fall back to 10000.
    """
    try:
        return int(os.getenv("PORT", str(default)))
    except ValueError:
        return default


def get_env_name(default: str = "dev") -> str:
    return os.getenv("ENV_NAME", default)


def get_bot_name(default: str = "C1C-Recruitment") -> str:
    return os.getenv("BOT_NAME", default)


def get_admin_ids() -> List[int]:
    """
    ADMIN_IDS can be:
      - "123,456"
      - " [ 123  ,  456 ] "
      - "123"
    Non-ints are ignored.
    """
    raw = os.getenv("ADMIN_IDS", "")
    # replace common separators with commas, then split
    for ch in ["[", "]", " ", ";", "|"]:
        raw = raw.replace(ch, ",")
    parts = [p for p in raw.split(",") if p.strip()]
    ids: List[int] = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            pass
    return ids


def get_watchdog_stall_sec(default: int = 120) -> int:
    try:
        return int(os.getenv("WATCHDOG_STALL_SEC", str(default)))
    except ValueError:
        return default


def get_command_prefix(default: str = "rec") -> str:
    return os.getenv("COMMAND_PREFIX", default)
