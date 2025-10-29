"""Builders for the onboarding summary embeds."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Literal

import discord
from discord.utils import utcnow

from shared.sheets import onboarding_questions

_COLOUR = discord.Colour(0x1F8BFF)
_FOOTER = "blue flame lit • C1C"
log = logging.getLogger(__name__)

_DESCRIPTIONS = {
    "welcome": (
        "🔥 C1C • Welcome aboard!",
        "Thanks for sharing your details — our coordinators will match you soon.\n"
        "Keep your thread open until a recruiter confirms placement.",
    ),
    "promo": (
        "🔥 C1C • Promo request received",
        "Got your request! A coordinator will review your move and follow up here.\n"
        "Please leave the thread unlocked until we reply.",
    ),
}


def build_summary_embed(
    flow: Literal["welcome", "promo"],
    answers: dict[str, Any],
    author: discord.Member,
    schema_hash: str,
) -> discord.Embed:
    """Return the C1C-branded summary embed for ``flow``."""

    title, description = _DESCRIPTIONS[flow]
    embed = discord.Embed(title=title, description=description, colour=_COLOUR, timestamp=utcnow())
    embed.set_footer(text=_FOOTER)

    if author:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name, icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)

    questions = onboarding_questions.get_questions(flow)
    expected_hash = onboarding_questions.schema_hash(flow)
    if schema_hash and schema_hash != expected_hash:
        log.warning(
            "onboarding.summary.schema_mismatch %s",
            {"flow": flow, "expected": expected_hash, "received": schema_hash},
        )

    rendered_qids: set[str] = set()
    for question in questions:
        value = _format_answer(question.type, answers.get(question.qid))
        if not value:
            continue
        rendered_qids.add(question.qid)
        if len(value) > 1024:
            value = f"{value[:1021]}..."
        embed.add_field(name=question.label, value=value, inline=False)

    for qid, stored in answers.items():
        if qid in rendered_qids:
            continue
        value = _stringify_collection(stored)
        if not value:
            continue
        if len(value) > 1024:
            value = f"{value[:1021]}..."
        embed.add_field(name=qid, value=value, inline=False)

    return embed


def _format_answer(qtype: str, stored: Any) -> str:
    if stored is None:
        return ""
    if qtype in {"short", "paragraph", "number"}:
        return str(stored).strip()
    if qtype == "single-select":
        if isinstance(stored, dict):
            label = stored.get("label") or stored.get("value")
            return str(label or "").strip()
        return str(stored).strip()
    return _stringify_collection(stored)


def _stringify_collection(stored: Any) -> str:
    if stored is None:
        return ""
    if isinstance(stored, dict):
        values = stored.get("values")
        if isinstance(values, Iterable):
            parts: list[str] = []
            for item in values:
                if isinstance(item, dict):
                    label = item.get("label") or item.get("value")
                    if label:
                        parts.append(str(label))
                elif item:
                    parts.append(str(item))
            if parts:
                return ", ".join(parts)
        label = stored.get("label")
        value = stored.get("value")
        for candidate in (label, value):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
    if isinstance(stored, Iterable) and not isinstance(stored, (str, bytes)):
        parts: list[str] = []
        for item in stored:
            if isinstance(item, dict):
                label = item.get("label") or item.get("value")
                if label:
                    parts.append(str(label))
            elif item:
                parts.append(str(item))
        return ", ".join(parts)
    return str(stored).strip()


__all__ = ["build_summary_embed"]
