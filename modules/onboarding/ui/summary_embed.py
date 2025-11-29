"""Builders for the onboarding summary embeds."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

import discord
from discord.utils import utcnow

from modules.recruitment.summary_embed import build_promo_summary_embed, build_welcome_summary_embed
from modules.recruitment.summary_map import SUMMARY_FRAME
from shared import theme
from shared.sheets import onboarding_questions
from shared.sheets.onboarding_questions import Question

_COLOUR = discord.Colour(0x1F8BFF)
_FOOTER = "blue flame lit • C1C"
log = logging.getLogger(__name__)

HIDE_TOKENS = {"0", "no", "none", "dunno"}

CVC_PRIORITY_LABELS: dict[str, str] = {
    "1": "Low",
    "2": "Low-Medium",
    "3": "Medium",
    "4": "High-Medium",
    "5": "High",
}

_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "welcome": (
        "🔥 C1C • Recruitment Summary",
        "Keep this thread open until a recruiter confirms placement.",
    ),
    "promo": (
        "🔥 C1C • Promo request received",
        "Got your request! A coordinator will review your move and follow up here.\n"
        "Please leave the thread unlocked until we reply.",
    ),
    "promo.r": (
        "🔥 C1C • Returning player request received",
        "Got your request! A coordinator will review your return and follow up here.\n"
        "Please leave the thread unlocked until we reply.",
    ),
    "promo.m": (
        "🔥 C1C • Member move request received",
        "Got your request! A coordinator will review your move and follow up here.\n"
        "Please leave the thread unlocked until we reply.",
    ),
}


def build_summary_embed(
    flow: str,
    answers: Mapping[str, Any],
    author: discord.abc.User | discord.Member | None = None,
    schema_hash: str | None = None,
    visibility: Mapping[str, Any] | None = None,
) -> discord.Embed:
    """Build a summary embed for the given onboarding flow."""

    if flow.startswith("promo"):
        try:
            return build_promo_summary_embed(flow, answers, visibility, author=author)
        except Exception:  # pragma: no cover - defensive fallback
            log.warning("promo.summary.fallback", exc_info=True)
            return _fallback_welcome_embed(author)

    # Fallback to the recruitment summary builder for any other flows.
    try:
        questions = onboarding_questions.get_questions(flow)
        expected_hash = onboarding_questions.schema_hash(flow)
        if schema_hash and schema_hash != expected_hash:
            log.warning(
                "onboarding.summary.schema_mismatch %s",
                {"flow": flow, "expected": expected_hash, "received": schema_hash},
            )

        # Welcome uses the sheet-driven, readability-spec layout.
        if flow == "welcome":
            return _build_welcome_summary(questions, answers, author, visibility)

        return _build_generic_summary(flow, questions, answers, author, visibility)
    except Exception:  # pragma: no cover - defensive fallback
        log.error("onboarding.summary.build_failed", exc_info=True, extra={"flow": flow})
        if flow == "welcome":
            return _fallback_welcome_embed(
                author if isinstance(author, discord.Member) else None
            )
        return _fallback_generic_embed(flow, author)


def _build_welcome_summary(
    questions: Iterable[Question],
    answers: Mapping[str, Any],
    author: discord.abc.User | discord.Member | None,
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> discord.Embed:
    """Build the welcome summary embed using the readability spec v2.1."""

    embed = _base_embed("welcome", author)

    by_qid: dict[str, Question] = {q.qid: q for q in questions}

    def formatted_answer(gid: str) -> str:
        question = by_qid.get(gid)
        if not question or _is_hidden(gid, visibility):
            return ""
        return _format_answer(question.type, answers.get(gid))

    def cleaned(gid: str) -> str:
        value = formatted_answer(gid)
        return "" if _is_effectively_empty(value) else value.strip()

    identity_lines: list[str] = []

    player = cleaned("w_ign")
    if player:
        identity_lines.append(_label("Player", player))

    power_value = formatted_answer("w_power")
    bracket_value = formatted_answer("w_level_detail")
    power = "" if _is_effectively_empty(power_value) else _format_short_number(answers.get("w_power") or power_value)
    bracket = "" if _is_effectively_empty(bracket_value) else bracket_value.strip()
    power_bracket = _format_inline_pair("Power", power, "Bracket", bracket)
    if power_bracket:
        identity_lines.append(power_bracket)

    playstyle = cleaned("w_playstyle")
    if playstyle:
        identity_lines.append(_label("Playstyle", playstyle))

    looking_for = cleaned("w_clan")
    if looking_for:
        identity_lines.append(_label("Looking for", looking_for))

    if identity_lines:
        embed.description = "\n\n".join([embed.description or "", "\n".join(identity_lines)])

    progress_lines: list[str] = []

    cb = cleaned("w_CB")
    if cb:
        progress_lines.append(_label("Clan Boss (one-key top chest)", cb))

    hydra_diff = cleaned("w_hydra_diff")
    hydra_clash_raw = formatted_answer("w_hydra_clash")
    hydra_clash = "" if _is_effectively_empty(hydra_clash_raw) else _format_short_number(answers.get("w_hydra_clash") or hydra_clash_raw)
    hydra_line = _format_inline_pair("Hydra", hydra_diff, "Avg Hydra Clash", hydra_clash)
    if hydra_line:
        progress_lines.append(hydra_line)

    chimera_diff = cleaned("w_chimera_diff")
    chimera_clash_raw = formatted_answer("w_chimera_clash")
    chimera_clash = "" if _is_effectively_empty(chimera_clash_raw) else _format_short_number(answers.get("w_chimera_clash") or chimera_clash_raw)
    chimera_line = _format_inline_pair("Chimera", chimera_diff, "Avg Chimera Clash", chimera_clash)
    if chimera_line:
        progress_lines.append(chimera_line)

    if progress_lines:
        embed.add_field(name="🧩 Progress & Bossing", value="\n".join(progress_lines), inline=False)

    war_lines: list[str] = []

    siege_raw = formatted_answer("w_siege")
    siege_display = siege_raw.strip() if siege_raw else "No"
    war_lines.append(_label("Siege participation", siege_display or "No"))

    siege_detail = cleaned("w_siege_detail")
    participates = not _is_effectively_empty(siege_raw) and siege_display.lower() not in {"no", "none"}
    if participates and siege_detail:
        war_lines.append(_label("Siege setup", siege_detail))

    cvc_raw = formatted_answer("w_cvc")
    cvc_priority = "" if _is_effectively_empty(cvc_raw) else CVC_PRIORITY_LABELS.get(cvc_raw.strip(), cvc_raw.strip())
    cvc_points_raw = formatted_answer("w_cvc_points")
    cvc_points = "" if _is_effectively_empty(cvc_points_raw) else _format_short_number(answers.get("w_cvc_points") or cvc_points_raw)
    cvc_line = _format_inline_pair("CvC priority", cvc_priority, "Minimum CvC points", cvc_points)
    if cvc_line:
        war_lines.append(cvc_line)

    if war_lines:
        embed.add_field(name="⚔️ War Modes", value="\n".join(war_lines), inline=False)

    notes_lines: list[str] = []

    progression = cleaned("w_level")
    if progression:
        if len(progression) > 200:
            progression = progression[:200]
        notes_lines.append(_label("Progression (self-feel)", progression))

    origin = cleaned("w_origin")
    if origin:
        notes_lines.append(_label("Heard about C1C from", origin))

    if notes_lines:
        embed.add_field(name="🧭 Notes", value="\n".join(notes_lines), inline=False)

    return embed


def _build_generic_summary(
    flow: str,
    questions: Iterable[Question],
    answers: Mapping[str, Any],
    author: discord.abc.User | discord.Member | None,
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> discord.Embed:
    title, description = _description_for_flow(flow)
    embed = discord.Embed(title=title, description=description, colour=_COLOUR, timestamp=utcnow())
    embed.set_footer(text=_FOOTER)

    if author:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name, icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)

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


def _description_for_flow(flow: str) -> tuple[str, str]:
    if flow == "welcome":
        return _DESCRIPTIONS["welcome"]
    if flow.startswith("promo"):
        return _DESCRIPTIONS.get(flow, _DESCRIPTIONS["promo"])
    return _DESCRIPTIONS.get(flow, _DESCRIPTIONS["welcome"])


def _base_embed(flow: str, author: discord.abc.User | discord.Member | None) -> discord.Embed:
    colour = _COLOUR
    title, description = _description_for_flow(flow)

    if flow == "welcome":
        icon_token = theme.get_icon(SUMMARY_FRAME.get("icon", ""))
        title = SUMMARY_FRAME.get("title", title)
        if icon_token:
            title = f"{icon_token} {title}"
        description = SUMMARY_FRAME.get("description", description)
        colour_name = SUMMARY_FRAME.get("color", "c1c_blue")
        colour = getattr(theme.colors, colour_name, _COLOUR)

    embed = discord.Embed(title=title, description=description, colour=colour, timestamp=utcnow())
    embed.set_footer(text=_FOOTER)

    if author:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name, icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)
    return embed


def _fallback_welcome_embed(author: discord.Member | None) -> discord.Embed:
    embed = _base_embed("welcome", author)
    embed.description = "Summary unavailable — see logs"
    return embed


def _fallback_generic_embed(
    flow: str, author: discord.abc.User | discord.Member | None
) -> discord.Embed:
    embed = _base_embed(flow, author)
    embed.description = "Summary unavailable — see logs"
    return embed


def _label(label: str, value: str) -> str:
    return f"**{label}:** {value}"


def _format_inline_pair(label_left: str, value_left: str | None, label_right: str, value_right: str | None) -> str:
    parts: list[str] = []
    if value_left:
        parts.append(_label(label_left, value_left))
    if value_right:
        parts.append(_label(label_right, value_right))
    return " • ".join(parts)


def _format_short_number(raw: object) -> str:
    # Accept str or numeric.
    if raw is None:
        return ""
    if isinstance(raw, str):
        raw = raw.strip().replace(",", "")
        if not raw:
            return ""
        try:
            value = float(raw)
        except ValueError:
            return str(raw)
    else:
        value = float(raw)

    if value < 1_000:
        return str(int(value))

    if value < 1_000_000:
        value_k = value / 1_000.0
        text = f"{value_k:.1f}"
        if text.endswith(".0"):
            text = text[:-2]
        return f"{text} K"

    value_m = value / 1_000_000.0
    text = f"{value_m:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text} M"


def _format_answer(qtype: str, stored: Any) -> str:
    """Format answers similar to the existing onboarding rendering."""

    if stored is None:
        return ""

    if qtype == "bool":
        if isinstance(stored, str):
            normalized = stored.strip().lower()
            if normalized in {"no", "false", "0", "none", ""}:
                return "No"
            return "Yes"
        return "Yes" if bool(stored) else "No"

    if qtype in {"short", "long"}:
        text = str(stored).strip()
        return text

    if qtype == "single":
        return _stringify_collection(stored)

    if qtype == "multi":
        if isinstance(stored, list):
            parts = [_stringify_collection(item) for item in stored]
            parts = [p for p in parts if p]
            return ", ".join(parts)
        return _stringify_collection(stored)

    return _stringify_collection(stored)


def _stringify_collection(stored: Any) -> str:
    if stored is None:
        return ""
    if isinstance(stored, bool):
        return "Yes" if stored else "No"
    if isinstance(stored, str):
        return stored.strip()
    if isinstance(stored, Mapping):
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


def _is_effectively_empty(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return normalized in HIDE_TOKENS


__all__ = ["build_summary_embed"]
