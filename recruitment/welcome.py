"""Welcome command integration bridged from the legacy Matchmaker bot."""

from __future__ import annotations

from typing import Dict, Iterable

from discord.ext import commands

from sheets import recruitment as sheets_recruitment
from shared.coreops_rbac import get_admin_role_ids, get_staff_role_ids

from . import ensure_loaded


async def setup(bot: commands.Bot) -> None:
    legacy = await ensure_loaded(bot)
    welcome_cog = getattr(legacy, "welcome_cog", None)
    if welcome_cog is None:
        return

    def _rows() -> Iterable[Dict]:
        return sheets_recruitment.fetch_welcome_templates()

    welcome_cog.get_rows = _rows  # type: ignore[attr-defined]
    allowed_roles = set(get_staff_role_ids()) | set(get_admin_role_ids())
    if allowed_roles:
        try:
            welcome_cog.allowed_role_ids = allowed_roles  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        welcome_cog.bot = bot  # type: ignore[attr-defined]
    except Exception:
        pass
