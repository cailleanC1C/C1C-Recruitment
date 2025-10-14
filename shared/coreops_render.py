# shared/coreops_render.py
from __future__ import annotations
import os, platform, time
import discord

def _hms(seconds: float) -> str:
    s = int(max(0, seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:d}h {m:02d}m {s:02d}s"

def build_digest_line(*, bot_name: str, env: str, uptime_sec: float, latency_s: float|None, last_event_age: float) -> str:
    lat = "—" if latency_s is None else f"{latency_s*1000:.0f}ms"
    return f"{bot_name} [{env}] · up {_hms(uptime_sec)} · rt {lat} · last {int(last_event_age)}s"

def build_health_embed(
    *,
    bot_name: str,
    env: str,
    version: str,
    uptime_sec: float,
    latency_s: float|None,
    last_event_age: float,
    keepalive_sec: int,
    stall_after_sec: int,
    disconnect_grace_sec: int,
) -> discord.Embed:
    e = discord.Embed(title=f"{bot_name} · health", colour=discord.Colour.blurple())
    e.add_field(name="env", value=env, inline=True)
    e.add_field(name="version", value=version, inline=True)
    e.add_field(name="uptime", value=_hms(uptime_sec), inline=True)

    e.add_field(name="latency", value=("—" if latency_s is None else f"{latency_s*1000:.0f} ms"), inline=True)
    e.add_field(name="last event", value=f"{int(last_event_age)} s", inline=True)
    e.add_field(name="keepalive", value=f"{keepalive_sec}s", inline=True)

    e.add_field(name="stall after", value=f"{stall_after_sec}s", inline=True)
    e.add_field(name="disconnect grace", value=f"{disconnect_grace_sec}s", inline=True)
    e.add_field(name="pid", value=str(os.getpid()), inline=True)

    e.set_footer(text=f"{platform.system()} {platform.release()}")
    return e

def build_env_embed(*, bot_name: str, env: str, version: str, cfg_meta: dict[str, object]) -> discord.Embed:
    e = discord.Embed(title=f"{bot_name} · env", colour=discord.Colour.dark_teal())
    e.add_field(name="env", value=env, inline=True)
    e.add_field(name="version", value=version, inline=True)
    src = cfg_meta.get("source", "runtime-only")
    status = cfg_meta.get("status", "ok")
    e.add_field(name="config", value=f"{src} ({status})", inline=True)
    # Show a few safe vars for sanity (no secrets)
    safe = []
    for k in ("COMMAND_PREFIX", "WATCHDOG_CHECK_SEC", "WATCHDOG_STALL_SEC", "WATCHDOG_DISCONNECT_GRACE_SEC"):
        v = os.getenv(k)
        if v:
            safe.append(f"{k}={v}")
    e.add_field(name="settings", value="\n".join(safe) if safe else "—", inline=False)
    return e
