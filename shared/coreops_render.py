# shared/coreops_render.py
from __future__ import annotations

import datetime as dt
import os
import platform
import time
from dataclasses import dataclass, field
from typing import Sequence

import discord

from shared.help import COREOPS_VERSION, build_coreops_footer

def _hms(seconds: float) -> str:
    s = int(max(0, seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:d}h {m:02d}m {s:02d}s"

def build_digest_line(*, bot_name: str, env: str, uptime_sec: float, latency_s: float | None, last_event_age: float) -> str:
    lat = "—" if latency_s is None else f"{latency_s*1000:.0f}ms"
    return f"{bot_name} [{env}] · up {_hms(uptime_sec)} · rt {lat} · last {int(last_event_age)}s"


@dataclass(frozen=True)
class DigestCacheError:
    bucket: str
    message: str


@dataclass(frozen=True)
class DigestCacheSummary:
    bucket: str = ""
    ttl: str | None = None
    retries: int = 0
    last_result: str | None = None
    error: str | None = None
    total: int | None = None
    stale: int | None = None
    recent_errors: int | None = None
    next_refresh_at: dt.datetime | None = None
    next_refresh_delta: int | None = None
    errors: Sequence[DigestCacheError] = ()


@dataclass(frozen=True)
class DigestSheetsSummary:
    last_success_age: int | None
    latency_ms: int | None
    retries: int | None
    next_refresh_at: dt.datetime | None
    next_refresh_delta: int | None
    last_error: str | None
    last_result: str | None


@dataclass(frozen=True)
class DigestEmbedData:
    bot_name: str
    env: str
    uptime_seconds: int | None
    latency_seconds: float | None
    gateway_age_seconds: int | None
    cache: DigestCacheSummary | None
    sheets: DigestSheetsSummary | None
    bot_version: str
    coreops_version: str = COREOPS_VERSION
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

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

    footer_notes = f" • {platform.system()} {platform.release()}"
    e.set_footer(text=build_coreops_footer(bot_version=version, notes=footer_notes))
    e.timestamp = dt.datetime.now(dt.timezone.utc)
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
    e.set_footer(text=build_coreops_footer(bot_version=version))
    e.timestamp = dt.datetime.now(dt.timezone.utc)
    return e


@dataclass(frozen=True)
class RefreshEmbedRow:
    bucket: str
    duration: str
    result: str
    retries: str
    error: str


def build_refresh_embed(
    *,
    scope: str,
    actor_display: str,
    trigger: str,
    rows: Sequence[RefreshEmbedRow],
    total_ms: int,
    bot_version: str,
    coreops_version: str = COREOPS_VERSION,
    now_utc: dt.datetime | None = None,
) -> discord.Embed:
    timestamp = now_utc or dt.datetime.now(dt.timezone.utc)
    embed = discord.Embed(
        title=f"Refresh • {scope}",
        colour=getattr(discord.Colour, "dark_theme", discord.Colour.dark_teal)(),
    )

    actor_line = f"actor: {actor_display.strip() or actor_display} • trigger: {trigger}"
    embed.description = actor_line

    headers = ["bucket", "duration", "result", "retries", "error"]
    data = [
        [
            row.bucket,
            row.duration,
            row.result,
            row.retries,
            row.error,
        ]
        for row in rows
    ]

    if data:
        widths = [len(header) for header in headers]
        for row in data:
            for idx, cell in enumerate(row):
                widths[idx] = max(widths[idx], len(cell))

        header_line = " | ".join(
            header.ljust(widths[idx]) for idx, header in enumerate(headers)
        )
        separator_line = "-+-".join("-" * width for width in widths)
        body_lines = [
            " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))
            for row in data
        ]
        table = "\n".join([header_line, separator_line, *body_lines])
    else:
        table = "no buckets"

    embed.add_field(name="Buckets", value=f"```{table}```", inline=False)
    footer_notes = f" · total: {total_ms}ms · {timestamp:%Y-%m-%d %H:%M:%S} UTC"
    embed.timestamp = timestamp
    embed.set_footer(
        text=build_coreops_footer(
            bot_version=bot_version,
            coreops_version=coreops_version,
            notes=footer_notes,
        )
    )
    return embed
