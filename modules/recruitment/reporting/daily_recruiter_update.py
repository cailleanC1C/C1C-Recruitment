from __future__ import annotations

import logging
import os
from datetime import datetime, time, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import discord
from discord.ext import tasks

from modules.common import feature_flags
from modules.common import runtime as runtime_helpers
from shared.config import (
    get_recruiter_role_ids,
    get_recruitment_sheet_id,
)
from shared.sheets.recruitment import (
    afetch_reports_tab,
    get_reports_tab_name,
)

log = logging.getLogger("c1c.recruitment.reporting.daily")

UTC = timezone.utc

_BOT_REFERENCE: Optional[discord.Client] = None


def feature_enabled() -> bool:
    """Return True when the recruitment_reports feature toggle is enabled."""

    try:
        return feature_flags.is_enabled("recruitment_reports")
    except Exception:
        log.debug("feature toggle lookup failed", exc_info=True)
        return False


def _parse_utc_time(value: str) -> time:
    text = (value or "").strip()
    if not text:
        raise ValueError("time string is empty")
    hour, minute = text.split(":", 1)
    return time(hour=int(hour), minute=int(minute), tzinfo=UTC)


def _scheduled_time() -> time:
    raw = os.getenv("REPORT_DAILY_POST_TIME", "09:30")
    try:
        return _parse_utc_time(raw)
    except Exception:
        log.warning(
            "invalid REPORT_DAILY_POST_TIME %r; falling back to 09:30", raw, exc_info=True
        )
        return time(hour=9, minute=30, tzinfo=UTC)


def _destination_channel_id() -> Optional[int]:
    raw = os.getenv("REPORT_RECRUITERS_DEST_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("invalid REPORT_RECRUITERS_DEST_ID=%r", raw)
        return None


def _role_mentions() -> Sequence[str]:
    try:
        role_ids = sorted(get_recruiter_role_ids())
    except Exception:
        log.debug("failed to resolve recruiter role IDs", exc_info=True)
        return ()
    return tuple(f"<@&{role_id}>" for role_id in role_ids)


HeadersMap = Dict[str, int]


def _normalize_header(label: str) -> str:
    return " ".join((label or "").strip().lower().replace("_", " ").split())


def _headers_map(row: Sequence[str]) -> HeadersMap:
    mapping: HeadersMap = {}
    for index, cell in enumerate(row):
        key = _normalize_header(str(cell or ""))
        if key:
            mapping[key] = index
    return mapping


def _column(row: Sequence[str], index: int | None) -> str:
    if index is None:
        return ""
    return str(row[index]) if 0 <= index < len(row) else ""


def _parse_int(text: str) -> int:
    try:
        return int(str(text).strip())
    except Exception:
        return 0


def _find_row_equals(rows: Sequence[Sequence[str]], column: int, needle: str) -> int:
    target = (needle or "").strip().lower()
    for idx, row in enumerate(rows):
        value = str(row[column] if column < len(row) else "").strip().lower()
        if value == target:
            return idx
    return -1


def _collect_block(
    rows: Sequence[Sequence[str]],
    *,
    start_row: int,
    stop_column: int,
    stop_value: str,
) -> List[Sequence[str]]:
    collected: List[Sequence[str]] = []
    stop_normalized = (stop_value or "").strip().lower()
    for idx in range(start_row + 1, len(rows)):
        row = rows[idx]
        value = str(row[stop_column] if stop_column < len(row) else "").strip().lower()
        if value == stop_normalized:
            break
        collected.append(row)
    return collected


def _collect_bracket_sections(
    rows: Sequence[Sequence[str]],
    *,
    start_row: int,
) -> Dict[str, List[Sequence[str]]]:
    wanted = [
        "elite end game",
        "early end game",
        "late game",
        "mid game",
        "early game",
        "beginners",
    ]
    desired = {label: [] for label in wanted}
    active: Optional[str] = None
    for idx in range(start_row, len(rows)):
        row = rows[idx]
        group = str(row[1] if len(row) > 1 else "").strip().lower()
        if group in desired:
            active = group
            continue
        if active is None:
            continue
        if not any(str(cell).strip() for cell in row):
            active = None
            continue
        desired[active].append(row)
    return desired


def _resolve_index(headers: HeadersMap, name: str) -> Optional[int]:
    normalized = _normalize_header(name)
    return headers.get(normalized)


def _format_line(headers: HeadersMap, row: Sequence[str]) -> Optional[str]:
    key_idx = _resolve_index(headers, "key")
    open_idx = _resolve_index(headers, "open spots")
    inactive_idx = _resolve_index(headers, "inactives")
    reserved_idx = _resolve_index(headers, "reserved spots")

    if None in {key_idx, open_idx, inactive_idx, reserved_idx}:
        return None

    label = _column(row, key_idx).strip()
    open_value = _parse_int(_column(row, open_idx))
    inactive_value = _parse_int(_column(row, inactive_idx))
    reserved_value = _parse_int(_column(row, reserved_idx))

    if (open_value, inactive_value, reserved_value) == (0, 0, 0):
        return None
    return (
        f"\U0001F539{label}: open {open_value} "
        f"| inactives {inactive_value} | reserved {reserved_value}"
    )


async def _fetch_report_rows() -> Tuple[List[List[str]], HeadersMap]:
    sheet_id = get_recruitment_sheet_id().strip()
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID is not configured")
    tab_name = get_reports_tab_name("Statistics")
    rows = await afetch_reports_tab(tab_name)
    matrix: List[List[str]] = [list(map(str, row)) for row in rows or []]
    headers = _headers_map(matrix[0]) if matrix else {}
    return matrix, headers


def _build_embed_from_rows(rows: Sequence[Sequence[str]], headers: HeadersMap) -> discord.Embed:
    embed = discord.Embed(
        title="Summary Open Spots",
        colour=discord.Colour.dark_teal(),
    )

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    embed.set_footer(text=f"last updated {timestamp} • daily UTC snapshot")

    general_index = _find_row_equals(rows, 0, "general overview")
    bracket_index = _find_row_equals(rows, 0, "per bracket")

    general_lines: List[str] = []
    if general_index != -1:
        stop_column = 0
        stop_value = "per bracket"
        block = _collect_block(
            rows,
            start_row=general_index,
            stop_column=stop_column,
            stop_value=stop_value,
        )
        for row in block:
            line = _format_line(headers, row)
            if line:
                general_lines.append(line)

    if general_lines:
        embed.add_field(
            name="General Overview",
            value="\n".join(general_lines),
            inline=False,
        )

    bracket_lines: List[str] = []
    if bracket_index != -1:
        sections = _collect_bracket_sections(rows, start_row=bracket_index + 1)
        order = [
            "elite end game",
            "early end game",
            "late game",
            "mid game",
            "early game",
            "beginners",
        ]
        for key in order:
            entries = sections.get(key) or []
            formatted = [line for row in entries if (line := _format_line(headers, row))]
            if not formatted:
                continue
            bracket_lines.append(f"**{key.title()}**")
            bracket_lines.extend(formatted)

    if bracket_lines:
        embed.add_field(
            name="Per Bracket",
            value="\n".join(bracket_lines),
            inline=False,
        )

    return embed


def _report_content(date_text: str) -> str:
    header = f"# Update {date_text}"
    mentions = list(_role_mentions())
    if mentions:
        return "\n".join([header, *mentions])
    return header


def _format_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".strip()
    return text or type(exc).__name__


async def _log_event(
    *,
    bot: discord.Client,
    actor: str,
    result: str,
    error: str,
    user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> None:
    dest_id = _destination_channel_id() or 0
    guild_id: Optional[int] = None
    if dest_id:
        try:
            channel = bot.get_channel(dest_id) or await bot.fetch_channel(dest_id)
        except Exception:
            channel = None
        if isinstance(channel, (discord.TextChannel, discord.Thread)) and channel.guild:
            guild_id = channel.guild.id
    date_text = datetime.now(UTC).strftime("%Y-%m-%d")
    parts = [
        "[report] recruiters",
        f"actor={actor}",
        f"guild={guild_id or '-'}",
        f"dest={dest_id or '-'}",
        f"date={date_text}",
        f"result={result}",
        f"error={error or '-'}",
    ]
    if user_id is not None:
        parts.insert(2, f"user={user_id}")
    if note:
        parts.append(f"note={note}")
    message = " \u2022 ".join(parts)
    try:
        await runtime_helpers.send_log_message(message)
    except Exception:
        log.debug("failed to send report log line", exc_info=True)


async def post_daily_recruiter_update(bot: discord.Client) -> Tuple[bool, str]:
    dest_id = _destination_channel_id()
    if not dest_id:
        return False, "dest-missing"

    await bot.wait_until_ready()

    try:
        channel = bot.get_channel(dest_id) or await bot.fetch_channel(dest_id)
    except Exception as exc:
        log.warning("failed to resolve report destination", exc_info=True)
        return False, _format_error(exc)

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "dest-not-found"

    rows: List[List[str]] = []
    headers: HeadersMap = {}
    fetch_error: Optional[str] = None
    try:
        rows, headers = await _fetch_report_rows()
    except Exception as exc:
        fetch_error = _format_error(exc)
        log.warning("failed to fetch recruiter report rows", exc_info=True)

    embed = _build_embed_from_rows(rows, headers)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    content = _report_content(today)

    try:
        await channel.send(content=content, embed=embed)
    except Exception as exc:
        log.warning("failed to send recruiter report", exc_info=True)
        return False, _format_error(exc)

    if fetch_error:
        return False, fetch_error
    return True, "-"


@tasks.loop(time=_scheduled_time())
async def scheduler_daily_recruiter_update() -> None:
    bot = _BOT_REFERENCE
    if bot is None:
        return
    ok, error = await post_daily_recruiter_update(bot)
    result = "ok" if ok else "fail"
    await _log_event(bot=bot, actor="scheduled", result=result, error=error)


async def ensure_scheduler_started(bot: discord.Client) -> None:
    global _BOT_REFERENCE
    _BOT_REFERENCE = bot

    if not feature_enabled():
        if scheduler_daily_recruiter_update.is_running():
            scheduler_daily_recruiter_update.cancel()
        return

    if not _destination_channel_id():
        if scheduler_daily_recruiter_update.is_running():
            scheduler_daily_recruiter_update.cancel()
        return

    if not scheduler_daily_recruiter_update.is_running():
        scheduler_daily_recruiter_update.start()


async def log_manual_result(
    *,
    bot: discord.Client,
    user_id: int,
    result: str,
    error: str,
    note: Optional[str] = None,
) -> None:
    await _log_event(
        bot=bot,
        actor="manual",
        result=result,
        error=error,
        user_id=user_id,
        note=note,
    )


__all__ = [
    "ensure_scheduler_started",
    "feature_enabled",
    "log_manual_result",
    "post_daily_recruiter_update",
    "scheduler_daily_recruiter_update",
]
