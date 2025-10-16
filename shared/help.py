# shared/help.py
from __future__ import annotations
import discord
import datetime as dt

COREOPS_VERSION = "1.0.0"


def build_coreops_footer(
    *, bot_version: str, coreops_version: str = COREOPS_VERSION, notes: str | None = None
) -> str:
    footer = f"Bot v{bot_version} · CoreOps v{coreops_version}"
    if notes:
        trimmed = notes.strip()
        if trimmed:
            # Preserve the caller's chosen separator (bullet, middot, etc.).
            footer = f"{footer}{notes}"
    return footer


def build_help_footer(*, bot_version: str) -> str:
    """Backward-compatible alias for callers expecting the legacy name."""

    return build_coreops_footer(bot_version=bot_version)


def build_help_embed(*, prefix: str, is_staff: bool, bot_version: str) -> discord.Embed:
    e = discord.Embed(title="🌿C1C Recruitment Helper · help", colour=discord.Color.blurple())
    user_cmds = [
        ("ping", "→ Basic reachability check"),
    ]
    staff_cmds = [
        ("health", "→ Detailed runtime/heartbeat info"),
        ("digest", "→ One-line status digest"),
        ("env", "→ Environment/config snapshot (no secrets)"),
    ]

    def fmt(items):
        return "\n".join(f"🔹 `!{prefix} {cmd}` — {desc}" for cmd, desc in items)

    e.add_field(name="Everyone", value=fmt(user_cmds) or "—", inline=False)
    if is_staff:
        e.add_field(name="Staff", value=fmt(staff_cmds) or "—", inline=False)
    footer_text = build_coreops_footer(bot_version=bot_version)
    e.set_footer(text=footer_text)
    e.timestamp = dt.datetime.now(dt.timezone.utc)
    return e
