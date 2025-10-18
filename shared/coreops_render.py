# shared/coreops_render.py
from __future__ import annotations

import datetime as dt
import os
import platform
from dataclasses import dataclass, field
from typing import Sequence

import discord

from shared.help import COREOPS_VERSION, build_coreops_footer
from shared.utils import humanize_duration

def _hms(seconds: float) -> str:
    s = int(max(0, seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:d}h {m:02d}m {s:02d}s"

def build_digest_line(*, bot_name: str, env: str, uptime_sec: float, latency_s: float | None, last_event_age: float) -> str:
    lat = "—" if latency_s is None else f"{latency_s*1000:.0f}ms"
    return f"{bot_name} [{env}] · up {_hms(uptime_sec)} · rt {lat} · last {int(last_event_age)}s"


_EM_DOT = " • "


def _sanitize_inline(text: object, *, allow_empty: bool = False) -> str:
    cleaned = str(text or "").strip()
    if not cleaned and not allow_empty:
        return "n/a"
    return cleaned.replace("`", "ʼ")


def _format_humanized(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"
    return humanize_duration(int(max(0, seconds)))


def _format_latency_ms(latency_ms: int | None) -> str:
    if latency_ms is None:
        return "n/a"
    return f"{int(latency_ms)}ms"


def _format_latency_seconds(latency_s: float | None) -> str:
    if latency_s is None:
        return "n/a"
    return f"{int(max(0, latency_s) * 1000):d}ms"


def _format_next_refresh(delta: int | None, at: dt.datetime | None) -> str:
    if delta is not None:
        if delta == 0:
            return "now"
        direction = "in" if delta > 0 else "ago"
        return f"{direction} {_format_humanized(abs(delta))}"
    if at is not None:
        try:
            return at.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return at.isoformat()
    return "n/a"


def _build_cache_field(summary: DigestCacheSummary | None) -> str:
    if summary is None:
        first_line = "buckets: n/a • stale: n/a • errors: n/a"
        next_line = "next refresh: n/a"
        return "\n".join([first_line, next_line])

    total_text = "n/a" if summary.total is None else str(summary.total)
    stale_text = "n/a" if summary.stale is None else str(summary.stale)
    error_text = "n/a" if summary.errors_total is None else str(summary.errors_total)
    lines = [f"buckets: {total_text} • stale: {stale_text} • errors: {error_text}"]

    if summary.errors_total and summary.errors_total > 0:
        for error in list(summary.errors)[:3]:
            bucket = _sanitize_inline(error.bucket, allow_empty=True) or "(unknown)"
            message = _sanitize_inline(error.message, allow_empty=True) or "n/a"
            lines.append(f"• {bucket}: {message}")

    next_refresh = _format_next_refresh(summary.next_refresh_delta, summary.next_refresh_at)
    lines.append(f"next refresh: {next_refresh}")
    return "\n".join(lines)


def _build_sheets_field(summary: DigestSheetsSummary | None) -> str:
    if summary is None:
        first_line = "last success: n/a • latency: n/a • retries: n/a"
        next_line = "next refresh: n/a"
        return "\n".join([first_line, next_line])

    success_text = _format_humanized(summary.last_success_age) if summary.last_success_age is not None else "n/a"
    if success_text != "n/a":
        success_text = f"{success_text} ago"
    latency_text = _format_latency_ms(summary.latency_ms)
    retries_text = "n/a" if summary.retries is None else str(summary.retries)

    lines = [f"last success: {success_text} • latency: {latency_text} • retries: {retries_text}"]

    if summary.last_error:
        lines.append(f"last error: {_sanitize_inline(summary.last_error)}")

    next_refresh = _format_next_refresh(summary.next_refresh_delta, summary.next_refresh_at)
    lines.append(f"next refresh: {next_refresh}")
    return "\n".join(lines)


def _format_description(data: DigestEmbedData) -> str:
    uptime = _format_humanized(data.uptime_seconds if data.uptime_seconds is not None else None)
    latency = _format_latency_seconds(data.latency_seconds)
    gateway = _format_humanized(data.gateway_age_seconds if data.gateway_age_seconds is not None else None)
    return (
        f"bot: {_sanitize_inline(data.bot_name)}{_EM_DOT}env: {_sanitize_inline(data.env)}{_EM_DOT}"
        f"uptime: {uptime}{_EM_DOT}latency: {latency}{_EM_DOT}gateway: last {gateway}"
    )


def build_digest_embed(data: DigestEmbedData) -> discord.Embed:
    colour_factory = getattr(discord.Colour, "blurple", None)
    color = colour_factory() if callable(colour_factory) else discord.Colour.blue()
    embed = discord.Embed(title="Digest", description=_format_description(data), colour=color)

    embed.add_field(name="Caches", value=_build_cache_field(data.cache), inline=False)
    embed.add_field(name="Sheets", value=_build_sheets_field(data.sheets), inline=False)

    timestamp = data.timestamp.astimezone(dt.timezone.utc)
    footer_text = (
        f"Bot v{_sanitize_inline(data.bot_version)} · "
        f"CoreOps v{_sanitize_inline(data.coreops_version)} · "
        f"{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    embed.set_footer(text=footer_text)
    embed.timestamp = timestamp
    return embed


@dataclass(frozen=True)
class DigestCacheError:
    bucket: str
    message: str


@dataclass(frozen=True)
class DigestCacheSummary:
    total: int | None = None
    stale: int | None = None
    errors_total: int | None = None
    next_refresh_at: dt.datetime | None = None
    next_refresh_delta: int | None = None
    errors: Sequence[DigestCacheError] = ()


@dataclass(frozen=True)
class DigestSheetsSummary:
    # Keep fields optional so we can fail-soft if any signal isn't available
    last_success_age: int | None = None
    latency_ms: int | None = None
    retries: int | None = None
    last_error: str | None = None
    next_refresh_at: dt.datetime | None = None
    next_refresh_delta: int | None = None


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
    footer_text = (
        f"Bot v{bot_version} · CoreOps v{coreops_version} · total: {total_ms} ms"
        if bot_version and coreops_version
        else f"total: {total_ms} ms"
    )
    embed.set_footer(text=footer_text)
    return embed
