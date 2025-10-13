# shared/help.py
from __future__ import annotations
import discord

def build_help_embed(*, prefix: str, is_staff: bool) -> discord.Embed:
    e = discord.Embed(title="🌿C1C Recruitment Helper · help", colour=discord.Colour.green())
    user_cmds = [
        ("🔹ping", "Basic reachability check"),
    ]
    staff_cmds = [
        ("🔹health", "→ Detailed runtime/heartbeat info"),
        ("🔹digest", "→ One-line status digest"),
        ("🔹env", "→ Environment/config snapshot (no secrets)"),
    ]

    def fmt(cmds):
        return "\n".join(f"`!{prefix} {c}` — {d}" for c, d in cmds)

    e.add_field(name="Everyone", value=fmt(user_cmds) or "—", inline=False)
    if is_staff:
        e.add_field(name="Staff", value=fmt(staff_cmds) or "—", inline=False)
    e.set_footer(text=f"🔹Bot v{bot_version}🔹CoreOps v1.0.0 🔹")
    return e
