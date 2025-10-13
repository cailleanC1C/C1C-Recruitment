# shared/help.py
from __future__ import annotations
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

def _vienna_now_str() -> str:
    """Return 'YYYY-MM-DD HH:MM Europe/Vienna' (fallback to UTC on any issue)."""
    try:
        if ZoneInfo is not None:
            tz = ZoneInfo("Europe/Vienna")
            return datetime.now(tz).strftime("%Y-%m-%d %H:%M Europe/Vienna")
    except Exception:
        pass
    # Fallback (should rarely happen)
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
def build_help_embed(*, prefix: str, is_staff: bool, bot_version: str) -> discord.Embed:
    e = discord.Embed(title="🌿C1C Recruitment Helper · help", colour=discord.Color.blurple())
    user_cmds = [
        ("🔹ping", "Basic reachability check"),
    ]
    staff_cmds = [
        ("🔹health", "→ Detailed runtime/heartbeat info"),
        ("🔹digest", "→ One-line status digest"),
        ("🔹env", "→ Environment/config snapshot (no secrets)"),
    ]
    fmt = lambda items: "\n".join(f"`!{prefix} {c}` — {d}" for c, d in items)
    e.add_field(name="Everyone", value=fmt(user_cmds) or "—", inline=False)
    if is_staff:
        e.add_field(name="Staff", value=fmt(staff_cmds) or "—", inline=False)
    e.set_footer(text=f"🔹Bot v{bot_version}🔹CoreOps v1.0.0 🔹")
    return e
