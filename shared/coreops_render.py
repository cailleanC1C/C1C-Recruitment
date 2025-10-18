# shared/coreops_render.py
from __future__ import annotations

import datetime as dt
import os
import platform
import time
from dataclasses import dataclass, field
from typing import Sequence

import discord

from shared.help import build_coreops_footer, COREOPS_VERSION
from shared.utils import humanize_duration

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
    total: int | None
    stale: int | None
    recent_errors: int | None
    next_refresh_at: dt.datetime | None
    next_refresh_delta: int | None
    errors: Sequence[DigestCacheError]


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


def _achievements_colour() -> discord.Colour:
    return discord.Colour.from_rgb(246, 181, 56)


def _format_duration(value: int | None) -> str:
    if value is None:
        return "n/a"
    text = humanize_duration(value)
    return "n/a" if text == "-" else text


def _format_latency_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{int(max(0.0, value) * 1000):d}ms"
    except Exception:
        return "n/a"


def _format_latency_ms(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{max(0, int(value))}ms"


def _format_count(value: int | None) -> str:
    return "n/a" if value is None else str(max(0, value))


def _format_next_refresh(at: dt.datetime | None, delta: int | None) -> str:
    if at is not None:
        try:
            timestamp = at.astimezone(dt.timezone.utc)
        except Exception:
            timestamp = None
        else:
            return timestamp.strftime("%Y-%m-%d %H:%M UTC")
    if delta is None:
        return "n/a"
    label = humanize_duration(abs(delta))
    if label == "-":
        label = "0s"
    if delta >= 0:
        return f"in {label}"
    return f"{label} ago"


def build_digest_embed(*, data: DigestEmbedData) -> discord.Embed:
    embed = discord.Embed(colour=_achievements_colour())
    embed.description = f"bot: {data.bot_name} • env: {data.env}"

    uptime_text = _format_duration(data.uptime_seconds)
    latency_text = _format_latency_seconds(data.latency_seconds)
    gateway_age = _format_duration(data.gateway_age_seconds)
    gateway_text = f"gateway: last {gateway_age}" if gateway_age != "n/a" else "gateway: n/a"
    metrics_line = f"uptime: {uptime_text} • latency: {latency_text} • {gateway_text}"
    embed.add_field(name="status", value=metrics_line, inline=False)

    if data.cache is None:
        cache_value = "n/a"
    else:
        cache_lines = [
            (
                "buckets: "
                f"{_format_count(data.cache.total)} total • "
                f"stale: {_format_count(data.cache.stale)} • "
                f"errors: {_format_count(data.cache.recent_errors)} in last 1h"
            ),
            f"next refresh: {_format_next_refresh(data.cache.next_refresh_at, data.cache.next_refresh_delta)}",
        ]
        for error in data.cache.errors:
            cache_lines.append(f"• {error.bucket}: {error.message}")
        cache_value = "\n".join(cache_lines)
    embed.add_field(name="Caches", value=cache_value, inline=False)

    if data.sheets is None:
        sheets_value = "n/a"
    else:
        sheets_lines = [
            (
                "last success: "
                f"{_format_duration(data.sheets.last_success_age)} • "
                f"latency: {_format_latency_ms(data.sheets.latency_ms)} • "
                f"retries: {_format_count(data.sheets.retries)}"
            ),
            f"next refresh: {_format_next_refresh(data.sheets.next_refresh_at, data.sheets.next_refresh_delta)}",
        ]
        status = (data.sheets.last_result or "").lower()
        if status.startswith("fail") or (data.sheets.last_error and status not in {"ok", "retry_ok"}):
            sheets_lines.append(f"last error: {data.sheets.last_error or data.sheets.last_result or 'n/a'}")
        sheets_value = "\n".join(sheets_lines)
    embed.add_field(name="Sheets", value=sheets_value, inline=False)

    footer_time = data.timestamp.astimezone(dt.timezone.utc)
    footer_text = (
        f"Bot v{data.bot_version} · CoreOps v{data.coreops_version} · "
        f"{footer_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    embed.set_footer(text=footer_text)
    embed.timestamp = footer_time
    return embed
