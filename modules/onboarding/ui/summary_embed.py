"""Builders for the onboarding summary embeds."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Literal, Mapping

import discord
from discord.utils import utcnow

from modules.recruitment.summary_embed import build_welcome_summary_embed
from modules.recruitment.summary_map import SUMMARY_FRAME
from shared import theme
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
    visibility: Mapping[str, Mapping[str, str]] | None = None,
) -> discord.Embed:
    """Return the C1C-branded summary embed for ``flow``."""

    if flow == "welcome":
        try:
            return build_welcome_summary_embed(answers, visibility, author=author)
        except Exception:
            log.exception("welcome.summary.build_failed", extra={"flow": flow})
            return _fallback_welcome_embed(author)

    return _build_onboarding_summary(flow, answers, author, schema_hash, visibility)


def _build_onboarding_summary(
    flow: Literal["welcome", "promo"],
    answers: Mapping[str, Any],
    author: discord.Member,
    schema_hash: str,
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> discord.Embed:
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
        if _is_hidden(question.qid, visibility):
            continue
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
        if _is_hidden(qid, visibility):
            continue
        value = _stringify_collection(stored)
        if not value:
            continue
        if len(value) > 1024:
            value = f"{value[:1021]}..."
        embed.add_field(name=qid, value=value, inline=False)

    return embed


def _fallback_welcome_embed(author: discord.Member | None) -> discord.Embed:
    icon_token = theme.get_icon(SUMMARY_FRAME.get("icon", ""))
    title = SUMMARY_FRAME.get("title", "C1C • Recruitment Summary")
    if icon_token:
        title = f"{icon_token} {title}"

    colour_name = SUMMARY_FRAME.get("color", "c1c_blue")
    colour = getattr(theme.colors, colour_name, theme.colors.c1c_blue)

    embed = discord.Embed(
        title=title,
        description="Summary unavailable — see logs",
        colour=colour,
    )

    footer = SUMMARY_FRAME.get("footer")
    if footer:
        embed.set_footer(text=footer)

    if author:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name or "", icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)

    return embed


def _format_answer(qtype: str, stored: Any) -> str:
    if stored is None:
        return ""
    if qtype in {"short", "paragraph", "number"}:
        return str(stored).strip()
    if qtype == "bool":
        if isinstance(stored, bool):
            return "Yes" if stored else "No"
        text = str(stored).strip()
        lowered = text.lower()
        if lowered in {"true", "yes", "y", "1"}:
            return "Yes"
        if lowered in {"false", "no", "n", "0"}:
            return "No"
        return text
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


def _is_hidden(qid: str, visibility: Mapping[str, Mapping[str, str]] | None) -> bool:
    if not visibility:
        return False
    state = visibility.get(qid, {}).get("state")
    return state == "skip"


__all__ = ["build_summary_embed"]
