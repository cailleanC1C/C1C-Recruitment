from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence, TYPE_CHECKING

import discord

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from modules.onboarding.sessions import Session


_MAX_PARAGRAPH_LEN = 300
_MAX_PARAGRAPH_TOTAL = 1020
_COLOUR = discord.Colour(0x3A74D8)


def _stringify_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    return text.strip()


def _stringify_collection(values: Iterable[object]) -> str:
    parts = []
    for item in values:
        if isinstance(item, (list, tuple, set)):
            nested = _stringify_collection(item)
            if nested:
                parts.append(nested)
            continue
        text = _stringify_value(item)
        if text:
            parts.append(text)
    return ", ".join(parts)


def _normalise_answer(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        return _stringify_collection(value)
    if isinstance(value, dict):
        # prefer explicit label/value ordering for structured answers
        for key in ("label", "value", "text"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return _normalise_answer(candidate)
        return _stringify_collection(value.values())
    return _stringify_value(value)


def _ensure_utc(timestamp: datetime | None) -> datetime:
    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def build_summary_embed(session: "Session", questions: Sequence[dict]) -> discord.Embed:
    """Build the final onboarding summary embed."""

    embed = discord.Embed(title="🎉 Welcome Summary", colour=_COLOUR)

    answered = 0
    para_total = 0
    answers = getattr(session, "answers", {})

    for question in questions:
        gid = question.get("gid")
        if not gid or gid not in answers:
            continue

        raw_value = answers[gid]
        if raw_value in (None, "", "—", []):
            continue

        label = question.get("label") or gid
        normalised = _normalise_answer(raw_value)
        if not normalised:
            continue

        qtype = (question.get("type") or "").strip().lower()
        value = normalised

        if qtype == "paragraph":
            value = value[:_MAX_PARAGRAPH_LEN]
            remaining = _MAX_PARAGRAPH_TOTAL - para_total
            if remaining <= 0:
                continue
            if len(value) > remaining:
                value = value[:remaining]
            para_total += len(value)
            if not value:
                continue

        embed.add_field(name=f"**{label}**", value=value, inline=False)
        answered += 1

    timestamp = _ensure_utc(getattr(session, "completed_at", None))
    embed.timestamp = timestamp
    footer_text = (
        f"🕓 Completed • {timestamp:%b %d %Y %H:%M UTC} | Total Questions Answered: {answered}"
    )
    embed.set_footer(text=footer_text)
    return embed


__all__ = ["build_summary_embed"]
