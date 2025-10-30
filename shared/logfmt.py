"""Human-friendly logging helpers and templates for Discord posts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

import discord

from shared.config import (
    get_log_include_numeric_ids,
    get_log_refresh_render_mode,
)

__all__ = [
    "LOG_EMOJI",
    "BucketResult",
    "channel_label",
    "user_label",
    "guild_label",
    "fmt_duration",
    "fmt_count",
    "human_reason",
    "LogTemplates",
]

LOG_EMOJI = {
    "success": "✅",
    "info": "🛈",
    "refresh": "♻️",
    "watchdog": "🐶",
    "security": "🔐",
    "scheduler": "🧭",
    "warning": "⚠️",
    "error": "❌",
}


def _append_id(label: str, numeric_id: Optional[int]) -> str:
    if not numeric_id:
        return label
    if not get_log_include_numeric_ids():
        return label
    return f"{label} ({numeric_id})"


def _clean_name(name: Optional[str], default: str) -> str:
    if not name:
        return default
    text = str(name).strip()
    return text or default


def channel_label(guild: Optional[discord.Guild], cid: Optional[int]) -> str:
    """Return a human-friendly label for a guild channel or thread."""

    if guild is None or cid is None:
        return _append_id("#unknown", cid)

    channel = guild.get_channel(cid)
    thread: Optional[discord.Thread] = None
    if channel is None:
        try:
            thread = guild.get_thread(cid)  # type: ignore[attr-defined]
        except AttributeError:
            thread = None
        except Exception:
            thread = None
        if thread is not None:
            channel = thread

    if isinstance(channel, discord.Thread):
        parent = getattr(channel, "parent", None)
        parent_name = _clean_name(getattr(parent, "name", None), "unknown")
        thread_name = _clean_name(channel.name, "thread")
        label = f"#{parent_name} › {thread_name}"
        return _append_id(label, cid)

    if isinstance(channel, discord.abc.GuildChannel):
        name = _clean_name(getattr(channel, "name", None), "channel")
        category = getattr(channel, "category", None)
        if category is not None:
            cat_name = _clean_name(getattr(category, "name", None), "category")
            label = f"#{cat_name} › {name}"
        else:
            label = f"#{name}"
        return _append_id(label, cid)

    return _append_id("#unknown", cid)


def user_label(guild: Optional[discord.Guild], uid: Optional[int]) -> str:
    """Return a human label for a guild user/member."""

    if uid is None:
        return "unknown"
    if guild is None:
        return _append_id("unknown", uid)
    getter = getattr(guild, "get_member", None)
    member = getter(uid) if callable(getter) else None
    if member is None:
        return _append_id("unknown", uid)
    display = _clean_name(getattr(member, "display_name", None), "unknown")
    return _append_id(display, uid)


def guild_label(bot: discord.Client, gid: Optional[int]) -> str:
    """Return a human label for a guild known to the bot."""

    if gid is None:
        return "unknown guild"
    guild = bot.get_guild(gid)
    if guild is None:
        return _append_id("unknown guild", gid)
    name = _clean_name(getattr(guild, "name", None), "guild")
    return _append_id(name, gid)


def _format_unit(value: float, unit: str) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}{unit}"
    return f"{value:.1f}{unit}"


def fmt_duration(value: float | int) -> str:
    """Format a duration expressed in milliseconds or seconds."""

    try:
        raw = float(value)
    except (TypeError, ValueError):
        return "0s"
    seconds = raw
    if raw > 120:  # assume milliseconds if clearly above 2 minutes when treated as seconds
        seconds = raw / 1000.0 if raw >= 1000 else raw
    if seconds < 0:
        seconds = 0.0
    if seconds < 60:
        return _format_unit(seconds, "s")
    minutes = seconds / 60.0
    if minutes < 60:
        return _format_unit(minutes, "m")
    hours = minutes / 60.0
    return _format_unit(hours, "h")


def fmt_count(value: Optional[int]) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


_HTTP_ERROR_CODES = {
    50001: "Missing Access",
    50013: "Missing Permissions",
    50035: "Invalid Form Body",
    50073: "Cannot Send Messages to This User",
    50083: "Webhooks Rate Limited",
}


def human_reason(exc_or_msg: object) -> str:
    """Normalize Discord HTTP errors to human-friendly text."""

    if exc_or_msg is None:
        return "-"
    if isinstance(exc_or_msg, str):
        text = " ".join(exc_or_msg.split())
        return text or "-"
    if isinstance(exc_or_msg, discord.HTTPException):
        status = getattr(exc_or_msg, "status", None)
        code = getattr(exc_or_msg, "code", None)
        base = _HTTP_ERROR_CODES.get(code, exc_or_msg.__class__.__name__)
        suffix = ""
        if status or code:
            suffix = f" ({status or '?'}" + (f"/{code}" if code else "") + ")"
        detail = " ".join(str(getattr(exc_or_msg, "text", "")).split())
        if detail:
            return f"{base}{suffix}: {detail}"
        return f"{base}{suffix}".strip()
    if isinstance(exc_or_msg, Exception):
        text = " ".join(str(exc_or_msg).split())
        label = exc_or_msg.__class__.__name__
        return f"{label}: {text}" if text else label
    return "-"


@dataclass(frozen=True)
class BucketResult:
    name: str
    status: str
    duration_s: float
    item_count: Optional[int]
    ttl_ok: Optional[bool]
    retries: Optional[int] = None
    reason: Optional[str] = None

    @property
    def ok(self) -> bool:
        normalized = self.status.lower().strip()
        return normalized in {"ok", "success"}


class LogTemplates:
    """Factory helpers for humanized log messages."""

    @staticmethod
    def scheduler(*, intervals: Mapping[str, str], upcoming: Mapping[str, str]) -> str:
        cadence = " • ".join(f"{key}={value}" for key, value in intervals.items()) or "-"
        next_parts = " • ".join(f"{key}={value}" for key, value in upcoming.items()) or "-"
        return (
            f"{LOG_EMOJI['scheduler']} **Scheduler** — "
            f"intervals: {cadence} • next: {next_parts}"
        )

    @staticmethod
    def scheduler_failure(*, job: str, reason: str) -> str:
        detail = reason or "-"
        return (
            f"{LOG_EMOJI['error']} **Scheduler** — failure • job={job} • reason={detail}"
        )

    @staticmethod
    def allowlist(*, allowed: Sequence[str], connected: Sequence[str], ok: bool) -> str:
        emoji = LOG_EMOJI["success"] if ok else LOG_EMOJI["warning"]
        allowed_text = ", ".join(allowed) or "—"
        connected_text = ", ".join(connected) or "—"
        state = "verified" if ok else "warning"
        return (
            f"{emoji} **Guild allow-list** — {state} • "
            f"allowed=[{allowed_text}] • connected=[{connected_text}]"
        )

    @staticmethod
    def allowlist_violation(*, allowed: Sequence[str], offending: Sequence[str]) -> str:
        allowed_text = ", ".join(allowed) or "—"
        offending_text = ", ".join(offending) or "—"
        return (
            f"{LOG_EMOJI['error']} **Guild allow-list** — violation • "
            f"connected=[{offending_text}] • allowed=[{allowed_text}]"
        )

    @staticmethod
    def watchdog(*, interval_s: int, stall_s: int, disconnect_grace_s: int) -> str:
        return (
            f"{LOG_EMOJI['watchdog']} **Watchdog started** — "
            f"interval={interval_s}s • stall={stall_s}s • disconnect_grace={disconnect_grace_s}s"
        )

    @staticmethod
    def refresh(scope: str, buckets: Sequence[BucketResult], total_s: float) -> str:
        bucket_parts: list[str] = []
        for result in buckets:
            details: list[str] = [fmt_duration(result.duration_s)]
            if result.item_count is not None:
                details.append(fmt_count(result.item_count))
            if result.ttl_ok is True:
                details.append("ttl")
            elif result.ttl_ok is False:
                details.append("stale")
            if result.retries:
                details.append(f"{result.retries}× retry")
            if result.reason and not result.ok:
                details.append(result.reason)
            detail_text = ", ".join(details)
            bucket_parts.append(f"{result.name} {result.status} ({detail_text})")
        buckets_text = " • ".join(bucket_parts) if bucket_parts else "-"
        return (
            f"{LOG_EMOJI['refresh']} **Refresh** — "
            f"scope={scope} • {buckets_text} • total={fmt_duration(total_s)}"
        )

    @staticmethod
    def refresh_table(scope: str, buckets: Sequence[BucketResult], total_s: float) -> str:
        header = f"{LOG_EMOJI['refresh']} Refresh • {scope} — total {fmt_duration(total_s)}"
        lines = ["bucket result items ttl duration"]
        for result in buckets:
            ttl_text = "yes" if result.ttl_ok else ("no" if result.ttl_ok is False else "?")
            lines.append(
                " ".join(
                    [
                        result.name,
                        result.status,
                        fmt_count(result.item_count),
                        ttl_text,
                        fmt_duration(result.duration_s),
                    ]
                )
            )
        table = "\n".join(lines)
        return "\n".join([header, f"```text\n{table}\n```"])

    @staticmethod
    def report(
        *,
        kind: str,
        actor: str,
        user: str,
        guild: str,
        dest: str,
        date: str,
        ok: bool,
        reason: Optional[str],
    ) -> str:
        emoji = LOG_EMOJI["success"] if ok else LOG_EMOJI["error"]
        reason_text = reason or "-"
        return (
            f"{emoji} **Report: {kind}** — actor={actor} • user={user} • "
            f"guild={guild} • dest={dest} • date={date} • reason={reason_text}"
        )

    @staticmethod
    def cache(
        *,
        bucket: str,
        ok: bool,
        duration_s: float,
        retries: Optional[int],
        reason: Optional[str],
    ) -> str:
        emoji = LOG_EMOJI["refresh"]
        status = "OK" if ok else "FAIL"
        details: list[str] = [fmt_duration(duration_s)]
        if retries:
            details.append(f"{fmt_count(retries)} retries")
        if reason and not ok:
            details.append(reason)
        detail_text = " • ".join(details)
        return f"{emoji} **Cache: {bucket}** — {status} • {detail_text}"

    @staticmethod
    def cmd_error(*, command: str, user: str, reason: str) -> str:
        return (
            f"{LOG_EMOJI['warning']} **Command error** — cmd={command or '-'} "
            f"• user={user or '-'} • reason={reason or '-'}"
        )

    @staticmethod
    def perm_sync(
        *,
        applied: int,
        errors: Mapping[str, int],
        threads_on: bool,
    ) -> str:
        emoji = LOG_EMOJI["security"]
        error_total = sum(errors.values())
        details = ", ".join(f"{count}× {reason}" for reason, count in errors.items())
        details = details or "-"
        return (
            f"{emoji} **Permission sync** — applied={fmt_count(applied)} • errors={fmt_count(error_total)} "
            f"• threads={'on' if threads_on else 'off'} • details: {details}"
        )

    @staticmethod
    def welcome(
        *,
        tag: str,
        recruit: str,
        channel: str,
        result: str,
        details: Sequence[str] | None,
    ) -> str:
        emoji = {
            "ok": LOG_EMOJI["success"],
            "partial": LOG_EMOJI["warning"],
            "error": LOG_EMOJI["error"],
        }.get(result, LOG_EMOJI["info"])
        extras = "; ".join(details or []) if details else "-"
        return (
            f"{emoji} **Welcome** — tag={tag} • recruit={recruit} • channel={channel} "
            f"• result={result} • details: {extras}"
        )

    @staticmethod
    def welcome_panel(
        *,
        actor: str,
        actor_display: str | None,
        thread: str,
        parent: str | None,
        result: str,
        details: Sequence[str] | None = None,
    ) -> str:
        palette = {
            "allowed": LOG_EMOJI["success"],
            "launched": LOG_EMOJI["success"],
            "saved": LOG_EMOJI["success"],
            "submitted": LOG_EMOJI["success"],
            "completed": LOG_EMOJI["success"],
            "started": LOG_EMOJI["success"],
            "reopened": LOG_EMOJI["success"],
            "refreshed": LOG_EMOJI["success"],
            "restarted": LOG_EMOJI["info"],
            "emoji_received": LOG_EMOJI["info"],
            "deduped": LOG_EMOJI["info"],
            "feature_disabled": LOG_EMOJI["warning"],
            "role_gate": LOG_EMOJI["warning"],
            "scope_gate": LOG_EMOJI["warning"],
            "denied_role": LOG_EMOJI["warning"],
            "denied_perms": LOG_EMOJI["warning"],
            "ambiguous_target": LOG_EMOJI["warning"],
            "timeout": LOG_EMOJI["warning"],
            "inactive": LOG_EMOJI["warning"],
            "no_trigger": LOG_EMOJI["warning"],
            "wrong_scope": LOG_EMOJI["warning"],
            "panel_failed": LOG_EMOJI["error"],
            "launch_failed": LOG_EMOJI["error"],
            "error": LOG_EMOJI["error"],
        }
        emoji = palette.get(result, LOG_EMOJI["info"])
        actor_text = actor_display or actor or "<unknown>"
        thread_text = thread or "#unknown"
        detail_text = "; ".join(details or []) if details else "-"
        parent_text = f" • parent={parent}" if parent else ""
        return (
            f"{emoji} **Welcome panel** — actor={actor_text} • thread={thread_text}"
            f"{parent_text} • result={result} • details: {detail_text}"
        )

    @staticmethod
    def select_refresh_template(scope: str, buckets: Sequence[BucketResult], total_s: float) -> str:
        mode = get_log_refresh_render_mode()
        if mode == "table":
            return LogTemplates.refresh_table(scope, buckets, total_s)
        return LogTemplates.refresh(scope, buckets, total_s)
