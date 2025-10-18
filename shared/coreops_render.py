# shared/coreops_render.py
from __future__ import annotations

import datetime as dt
import os
import platform
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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


def _config_meta_extras(meta: object) -> Mapping[str, Any]:
    if isinstance(meta, Mapping):
        extras = meta.get("_extras")
        if isinstance(extras, Mapping):
            return extras
    return {}


def _format_short_id(value: object) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not digits:
        return None
    if len(digits) <= 4:
        return digits
    return f"(…{digits[-4:]})"


def _format_sheet_entries(entries: Sequence[Mapping[str, Any]]) -> str:
    if not entries:
        return "n/a"

    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        label = _sanitize_inline(entry.get("label") or f"Sheet #{index}")
        connected_flag = entry.get("connected")
        if connected_flag is None:
            sheet_id = entry.get("id")
            connected = bool(sheet_id)
        else:
            connected = bool(connected_flag)
        emoji = "✅" if connected else "⚠️"
        status_text = "Connected" if connected else "Missing"

        friendly = entry.get("friendly_name")
        fallback = entry.get("fallback_name")
        short_id = _format_short_id(entry.get("id"))

        detail_parts: list[str] = []
        if isinstance(friendly, str) and friendly.strip():
            detail_parts.append(_sanitize_inline(friendly))
        elif isinstance(fallback, str) and fallback.strip():
            detail_parts.append(_sanitize_inline(fallback))

        if not detail_parts and short_id:
            detail_parts.append(short_id)
        elif detail_parts and not isinstance(friendly, str) and short_id:
            detail_parts.append(short_id)

        detail_text = ""
        if detail_parts:
            detail_text = f" *({' · '.join(detail_parts)})*"

        lines.append(f"- {label} → {emoji} {status_text}{detail_text}")

    return "\n".join(lines)


def _format_guild_access(entries: Sequence[Mapping[str, Any]], allowlist: Sequence[Mapping[str, Any]]) -> str:
    lines: list[str] = []

    connected_names = [
        _sanitize_inline(item.get("display") or item.get("name"))
        for item in entries
        if isinstance(item, Mapping)
    ]
    connected_names = [name for name in connected_names if name and name != "n/a"]
    connected_text = ", ".join(connected_names) if connected_names else "n/a"
    lines.append(f"- Connected guilds: {connected_text}")

    allow_count = len(allowlist)
    preview_text: str | None = None
    if allowlist:
        first = allowlist[0]
        if isinstance(first, Mapping):
            label = first.get("label")
            if isinstance(label, str) and label.strip():
                preview_text = _sanitize_inline(label)
            else:
                short_id = _format_short_id(first.get("id"))
                if short_id:
                    preview_text = f"Guild {short_id} (unresolved)"

    allow_line = f"- Allow-listed: {allow_count} total"
    if preview_text:
        allow_line += f" — {preview_text}"
    lines.append(allow_line)

    return "\n".join(lines)


def _map_source_label(source: str) -> str:
    cleaned = source.strip()
    if not cleaned:
        return "Unknown"

    lowered = cleaned.lower()
    if "shared.config" in lowered or "env" in lowered:
        return "Environment variables"
    if "sheet" in lowered:
        return "Google Sheets"
    if "runtime" in lowered:
        return "Runtime defaults"
    if "config" in lowered and "http" not in lowered:
        return cleaned.replace("_", " ").title()
    return cleaned


def _format_overrides(meta: Mapping[str, Any]) -> str:
    keys: list[str] = []
    overrides = meta.get("overrides")
    if isinstance(overrides, Mapping):
        keys = [str(k).strip() for k in overrides.keys() if str(k).strip()]
    elif isinstance(overrides, (list, tuple, set)):
        keys = [str(k).strip() for k in overrides if str(k).strip()]

    if not keys:
        override_keys = meta.get("override_keys")
        if isinstance(override_keys, (list, tuple, set)):
            keys = [str(k).strip() for k in override_keys if str(k).strip()]

    count_hint = meta.get("overrides_count")
    count = None
    if isinstance(count_hint, int) and count_hint >= 0:
        count = count_hint

    filtered_keys = [k for k in keys if k]
    sorted_keys = sorted(filtered_keys, key=lambda value: value.lower())

    if count is None:
        count = len(sorted_keys)

    if count == 0:
        return "Overrides: none"

    display_keys = sorted_keys[:5]
    preview = ", ".join(_sanitize_inline(k) for k in display_keys)
    if len(sorted_keys) > len(display_keys) or (count and count > len(display_keys)):
        preview = f"{preview}, …" if preview else "…"

    plural = "key" if count == 1 else "keys"
    if preview:
        return f"Overrides: {count} {plural} — {preview}"
    return f"Overrides: {count} {plural}"


def _format_source(meta: Mapping[str, Any]) -> str:
    source_raw = str(meta.get("source") or "")
    source_text = _map_source_label(source_raw)
    loaded_line = f"Loaded from: {_sanitize_inline(source_text)}"
    overrides_line = _format_overrides(meta)
    if overrides_line:
        return "\n".join([loaded_line, overrides_line])
    return loaded_line


def _format_ops_channel(info: Mapping[str, Any]) -> str:
    configured = bool(info.get("id"))
    if not configured:
        return "Logs → ⚠️ Missing"

    label = info.get("label")
    short_id = _format_short_id(info.get("id"))
    detail = None
    if isinstance(label, str) and label.strip():
        detail = _sanitize_inline(label)
    elif short_id:
        detail = short_id

    suffix = f" *({detail})*" if detail else ""
    return f"Logs → ✅ Configured{suffix}"


def build_config_embed(
    snapshot: Mapping[str, Any],
    meta: Mapping[str, Any] | object,
    *,
    bot_version: str,
    coreops_version: str = COREOPS_VERSION,
) -> discord.Embed:
    extras = _config_meta_extras(meta)
    env = extras.get("environment") or snapshot.get("ENV_NAME") or "n/a"
    env_text = _sanitize_inline(env)

    connected_entries = []
    allow_entries = []
    sheet_entries = []
    ops_info: Mapping[str, Any] = {}

    raw_connected = extras.get("connected_guilds")
    if isinstance(raw_connected, Sequence) and not isinstance(raw_connected, (str, bytes)):
        connected_entries = [item for item in raw_connected if isinstance(item, Mapping)]

    raw_allow = extras.get("allowlist")
    if isinstance(raw_allow, Sequence) and not isinstance(raw_allow, (str, bytes)):
        allow_entries = [item for item in raw_allow if isinstance(item, Mapping)]

    raw_sheets = extras.get("sheets")
    if isinstance(raw_sheets, Sequence) and not isinstance(raw_sheets, (str, bytes)):
        sheet_entries = [item for item in raw_sheets if isinstance(item, Mapping)]

    raw_ops_info = extras.get("ops_channel")
    if isinstance(raw_ops_info, Mapping):
        ops_info = raw_ops_info

    colour_factory = getattr(discord.Colour, "blurple", None)
    colour = colour_factory() if callable(colour_factory) else discord.Colour.blue()

    connected_count = len(connected_entries)
    allow_count = len(allow_entries)
    description = (
        f"Environment: {env_text}"
        f" • Connected guilds: {connected_count}"
        f" • Allow-list: {allow_count}"
    )

    embed = discord.Embed(title="Config Overview", description=description, colour=colour)

    sheets_value = _format_sheet_entries(sheet_entries)
    embed.add_field(name="Sheets", value=sheets_value or "n/a", inline=False)

    guild_value = _format_guild_access(connected_entries, allow_entries)
    embed.add_field(name="Guild Access", value=guild_value or "n/a", inline=False)

    meta_mapping: Mapping[str, Any]
    if isinstance(meta, Mapping):
        meta_mapping = meta
    else:
        meta_mapping = {}
    source_value = _format_source(meta_mapping)
    embed.add_field(name="Source", value=source_value or "n/a", inline=False)

    ops_value = _format_ops_channel(ops_info)
    embed.add_field(name="Ops Channel", value=ops_value or "n/a", inline=False)

    footer_text = (
        f"Bot v{_sanitize_inline(bot_version)}"
        f" · CoreOps v{_sanitize_inline(coreops_version)}"
    )
    embed.set_footer(text=footer_text)
    return embed


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


def _format_next_eta(delta: int | None, at: dt.datetime | None) -> str:
    if delta is None and at is not None:
        try:
            delta = int((at - dt.datetime.now(dt.timezone.utc)).total_seconds())
        except Exception:
            delta = None
    if delta is None:
        return "n/a"
    if delta == 0:
        return "now"
    human = _format_humanized(abs(delta))
    if human == "n/a":
        return "n/a"
    return f"in {human}" if delta > 0 else f"{human} ago"


def _prefix_estimated(text: str, estimated: bool) -> str:
    if estimated and text not in {"n/a", "-"}:
        return f"~{text}"
    return text


def _build_sheets_field(entries: Sequence[DigestSheetEntry]) -> str:
    if not entries:
        return "n/a"

    lines = []
    for entry in entries:
        status = entry.status or "n/a"
        age_text = _prefix_estimated(
            _format_humanized(entry.age_seconds), entry.age_estimated
        )
        next_text = _prefix_estimated(
            _format_next_eta(entry.next_refresh_delta_seconds, entry.next_refresh_at),
            entry.next_refresh_estimated,
        )
        retries_text = "n/a" if entry.retries is None else str(entry.retries)
        error_raw = _sanitize_inline(entry.error, allow_empty=True)
        error_text = error_raw if error_raw else "n/a"
        line = (
            f"{entry.display_name} — {status} · "
            f"age {age_text} · next {next_text} · "
            f"retries {retries_text} · err {error_text}"
        )
        lines.append(line)
    return "\n".join(lines)


def _build_sheets_client_field(summary: DigestSheetsClientSummary | None) -> str:
    if summary is None:
        return "last success: n/a · latency: n/a · retries: n/a"

    success_text = _format_humanized(summary.last_success_age)
    if success_text != "n/a":
        success_text = f"{success_text} ago"
    latency_text = _format_latency_ms(summary.latency_ms)
    retries_text = "n/a" if summary.retries is None else str(summary.retries)

    lines = [f"last success: {success_text} · latency: {latency_text} · retries: {retries_text}"]
    if summary.last_error:
        lines.append(f"last error: {_sanitize_inline(summary.last_error)}")
    return "\n".join(lines)


def _format_description(data: DigestEmbedData) -> str:
    uptime = _format_humanized(data.uptime_seconds if data.uptime_seconds is not None else None)
    latency = _format_latency_seconds(data.latency_seconds)
    gateway = _format_humanized(data.gateway_age_seconds if data.gateway_age_seconds is not None else None)
    return (
        f"{_sanitize_inline(data.env)}{_EM_DOT}uptime {uptime}{_EM_DOT}"
        f"latency {latency}{_EM_DOT}gateway last {gateway}"
    )


def build_digest_embed(data: DigestEmbedData) -> discord.Embed:
    colour_factory = getattr(discord.Colour, "blurple", None)
    color = colour_factory() if callable(colour_factory) else discord.Colour.blue()
    embed = discord.Embed(title="Digest", description=_format_description(data), colour=color)

    embed.add_field(name="Sheets", value=_build_sheets_field(data.sheets), inline=False)
    embed.add_field(name="Sheets client", value=_build_sheets_client_field(data.sheets_client), inline=False)

    tip_text = _maybe_build_tip(data.sheets)
    if tip_text:
        embed.add_field(name="​", value=tip_text, inline=False)

    footer_text = (
        f"Bot v{_sanitize_inline(data.bot_version)} · "
        f"CoreOps v{_sanitize_inline(data.coreops_version)}"
    )
    embed.set_footer(text=footer_text)
    return embed


def _maybe_build_tip(entries: Sequence[DigestSheetEntry]) -> str | None:
    if entries:
        return 'Need latest openings? run "!rec refresh clansinfo" and retry.'
    return None


@dataclass(frozen=True)
class DigestEmbedData:
    env: str
    uptime_seconds: int | None
    latency_seconds: float | None
    gateway_age_seconds: int | None
    sheets: Sequence[DigestSheetEntry]
    sheets_client: DigestSheetsClientSummary | None
    bot_version: str
    coreops_version: str = COREOPS_VERSION


@dataclass(frozen=True)
class DigestSheetEntry:
    display_name: str
    status: str
    age_seconds: int | None
    next_refresh_delta_seconds: int | None
    next_refresh_at: dt.datetime | None
    retries: int | None
    error: str | None
    age_estimated: bool = False
    next_refresh_estimated: bool = False


@dataclass(frozen=True)
class DigestSheetsClientSummary:
    last_success_age: int | None = None
    latency_ms: int | None = None
    retries: int | None = None
    last_error: str | None = None

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
