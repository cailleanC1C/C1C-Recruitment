# Shared CoreOps Inventory

## shared/coreops_cog.py
- Size: 100413 bytes

### First 40 lines
```python
"""CoreOps shared cog and RBAC helpers."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import sys
import time
from importlib import import_module
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import discord
from discord.ext import commands

from config.runtime import (
    get_bot_name,
    get_command_prefix,
    get_env_name,
    get_watchdog_check_sec,
    get_watchdog_disconnect_grace_sec,
    get_watchdog_stall_sec,
)
from shared import socket_heartbeat as hb
from shared.config import (
    get_allowed_guild_ids,
    get_config_snapshot,
    get_feature_toggles,
    reload_config,
    redact_value,
)
from shared.coreops_render import (
    ChecksheetEmbedData,
    ChecksheetSheetEntry,
    ChecksheetTabEntry,
    DigestEmbedData,
```

### Public symbols
- Classes: CoreOpsCog
- Functions: resolve_ops_log_channel_id
- Constants: UTC

### Importers
- modules/coreops/cog.py:7 — `from shared.coreops_cog import CoreOpsCog`
- shared/sheets/cache_scheduler.py:14 — `from shared.coreops_cog import resolve_ops_log_channel_id`

## shared/coreops_rbac.py
- Size: 9714 bytes

### First 40 lines
```python
"""Role helpers for CoreOps gating (Phase 2).

These mirror the legacy bots' behavior: role-based gating is done via role IDs
from the environment instead of user IDs. The helpers here intentionally ignore
non-numeric tokens so we can safely reuse old .env files without causing hard
crashes if a value is malformed.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Set, Tuple, Union

import discord
from discord.ext import commands

from shared.config import (
    get_admin_role_ids as _config_admin_roles,
    get_lead_role_ids as _config_lead_roles,
    get_recruiter_role_ids as _config_recruiter_roles,
    get_staff_role_ids as _config_staff_roles,
)

Memberish = Union[discord.abc.User, discord.Member]
ContextOrMember = Union[commands.Context, Memberish]

_DENIAL_LOG_THROTTLE_SEC = 30.0
_denial_log_cache: Dict[Tuple[Optional[int], str, Optional[int]], float] = {}
_ADMIN_FALLBACK_LOG_THROTTLE_SEC = 600.0
_admin_fallback_log_cache: Dict[Tuple[str, Optional[int]], float] = {}


def _suppress_denial(ctx: commands.Context) -> bool:
    return bool(getattr(ctx, "_coreops_suppress_denials", False))

logger = logging.getLogger(__name__)


def _member_role_ids(member: Memberish | None) -> Set[int]:
    if not isinstance(member, discord.Member):
```

### Public symbols
- Classes: _None_
- Functions: admin_only, can_view_admin, can_view_staff, get_admin_role_ids, get_lead_role_ids, get_recruiter_role_ids, get_staff_role_ids, guild_only_denied_msg, is_admin_member, is_lead, is_recruiter, is_staff_member, ops_gate, ops_only
- Constants: _None_

### Importers
- app.py:23 — `from shared.coreops_rbac import (\n    admin_only,\n    get_admin_role_ids,\n    get_staff_role_ids,\n    is_admin_member,\n)`
- cogs/recruitment_recruiter.py:17 — `from shared.coreops_rbac import is_admin_member, is_recruiter`
- modules/recruitment/services/search.py:7 — `from shared.coreops_rbac import is_lead, is_recruiter`
- modules/recruitment/welcome.py:8 — `from shared.coreops_rbac import is_staff_member, is_admin_member`

## shared/coreops_render.py
- Size: 22950 bytes

### First 40 lines
```python
# shared/coreops_render.py
from __future__ import annotations

import datetime as dt
import os
import platform
from dataclasses import dataclass
from typing import Sequence

import discord

from shared.help import COREOPS_VERSION, build_coreops_footer
from shared.utils import humanize_duration

def _hms(seconds: float) -> str:
    s = int(max(0, seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:d}h {m:02d}m {s:02d}s"

def build_digest_line(
    *, env: str, uptime_sec: float | None, latency_s: float | None, last_event_age: float | None
) -> str:
    uptime_text = _format_humanized(int(uptime_sec) if uptime_sec is not None else None)
    latency_text = _format_latency_seconds(latency_s)
    gateway_text = _format_humanized(int(last_event_age) if last_event_age is not None else None)
    return (
        f"env: {_sanitize_inline(env)} · uptime: {uptime_text} · "
        f"latency: {latency_text} · gateway: last {gateway_text}"
    )


_EM_DOT = " • "


def _sanitize_inline(text: object, *, allow_empty: bool = False) -> str:
    cleaned = str(text or "").strip()
    if not cleaned and not allow_empty:
        return "n/a"
    return cleaned.replace("`", "ʼ")
```

### Public symbols
- Classes: ChecksheetEmbedData, ChecksheetSheetEntry, ChecksheetTabEntry, DigestEmbedData, DigestSheetEntry, DigestSheetsClientSummary, RefreshEmbedRow
- Functions: build_checksheet_tabs_embed, build_config_embed, build_digest_embed, build_digest_line, build_env_embed, build_health_embed, build_refresh_embed
- Constants: _None_

### Importers
- modules/common/runtime.py:56 — `from shared.coreops_render import build_refresh_embed, RefreshEmbedRow`
- shared/coreops_cog.py:36 — `from shared.coreops_render import (\n    ChecksheetEmbedData,\n    ChecksheetSheetEntry,\n    ChecksheetTabEntry,\n    DigestEmbedData,\n    DigestSheetEntry,\n    DigestSheetsClientSummary,\n    RefreshEmbedRow,\n    build_config_embed,\n    build_checksheet_tabs_embed,\n    build_digest_embed,\n    build_digest_line,\n    build_health_embed,\n    build_refresh_embed,\n)`

## shared/coreops_prefix.py
- Size: 1033 bytes

### First 40 lines
```python
# shared/coreops_prefix.py
from __future__ import annotations

import re
from typing import Callable, Collection, Dict, Optional

import discord

AdminCheck = Callable[[discord.abc.User | discord.Member], bool]
_BANG_CMD_RE = re.compile(r"^!\s*([a-zA-Z]+)(?:\s|$)")


def _normalize_commands(commands: Collection[str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for name in commands:
        if not isinstance(name, str):
            continue
        lowered = name.lower().strip()
        if lowered:
            lookup[lowered] = name
    return lookup


def detect_admin_bang_command(
    message: discord.Message,
    *, commands: Collection[str], is_admin: AdminCheck
) -> Optional[str]:
    normalized = _normalize_commands(commands)
    if not normalized or not callable(is_admin) or not is_admin(message.author):
        return None
    raw = (message.content or "").strip()
    match = _BANG_CMD_RE.match(raw)
    if not match:
        return None
    cmd = match.group(1).lower()
    return normalized.get(cmd)
```

### Public symbols
- Classes: _None_
- Functions: detect_admin_bang_command
- Constants: _None_

### Importers
- app.py:22 — `from shared.coreops_prefix import detect_admin_bang_command`

Doc last updated: 2025-10-22 (v0.9.5)
