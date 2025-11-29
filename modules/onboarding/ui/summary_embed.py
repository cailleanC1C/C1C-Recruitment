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

    # Welcome uses the sheet-driven, readability-spec layout.
    if flow == "welcome":
        return _build_onboarding_summary(flow, answers, author, schema_hash, visibility)

    if flow.startswith("promo"):
        try:
            return build_promo_summary_embed(flow, answers, visibility, author=author)
        except Exception:  # pragma: no cover - defensive fallback
            log.warning("promo.summary.fallback", exc_info=True)
            return _fallback_welcome_embed(author)

    # Fallback to the recruitment summary builder for any other flows.
    try:
        return build_welcome_summary_embed(answers, visibility, author=author)
    except Exception:  # pragma: no cover - defensive fallback
        log.warning("welcome.summary.fallback", exc_info=True)
        return _fallback_welcome_embed(author)


def _build_onboarding_summary(
    flow: str,
    answers: Mapping[str, Any],
    author: discord.Member,
    schema_hash: str,
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> discord.Embed:
    """Build the sheet-driven welcome summary embed."""

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

    questions = onboarding_questions.get_questions(flow)
    expected_hash = onboarding_questions.schema_hash(flow)
    if schema_hash and schema_hash != expected_hash:
        log.warning(
            "onboarding.summary.schema_mismatch %s",
            {"flow": flow, "expected": expected_hash, "received": schema_hash},
        )

    # Build welcome summary fields according to the v2.1 spec.
    # We only apply the spec for the welcome flow; promo continues to use the
    # recruitment summary implementation for now.
    if flow == "welcome":
        fields = _build_welcome_fields(questions, answers, visibility)
        for field in fields:
            embed.add_field(**field)
        return embed

    # Fallback to the generic behavior if somehow called with a non-welcome flow.
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
        timestamp=utcnow(),
    )
    embed.set_footer(text=_FOOTER)

    if author:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name, icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)
    return embed


def _build_welcome_fields(
    questions: Iterable[Question],
    answers: Mapping[str, Any],
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> list[dict[str, Any]]:
    """Build embed fields for the welcome flow using the v2.1 spec."""

    # Map gid → Question for quick lookup.
    by_gid: dict[str, Question] = {q.qid: q for q in questions}

    def q(gid: str) -> Question | None:
        return by_gid.get(gid)

    def val(gid: str) -> str:
        question = q(gid)
        if question is None:
            return ""
        if _is_hidden(question.qid, visibility):
            return ""
        return _format_answer(question.type, answers.get(question.qid))

    def raw(gid: str) -> Any:
        return answers.get(gid)

    def cleaned(v: str) -> str:
        v = (v or "").strip()
        if not v:
            return ""
        # Hide “no / none / dunno / 0” except where the spec says otherwise.
        lowered = v.lower()
        if lowered in {"0", "no", "none", "dunno"}:
            return ""
        return v

    fields: list[dict[str, Any]] = []

    # 1. Identity & intent
    player = cleaned(val("w_ign"))
    if player:
        fields.append(_field("Player", player))

    power_raw = cleaned(val("w_power"))
    bracket_raw = cleaned(val("w_level_detail"))
    power_fmt = _format_number(power_raw) if power_raw else ""
    identity_line_parts: list[str] = []
    if power_fmt:
        identity_line_parts.append(power_fmt)
    if bracket_raw:
        identity_line_parts.append(bracket_raw)
    if identity_line_parts:
        fields.append(_field("Power • Bracket", " • ".join(identity_line_parts)))

    playstyle = cleaned(val("w_playstyle"))
    if playstyle:
        fields.append(_field("Playstyle", playstyle))

    looking_for = cleaned(val("w_clan"))
    if looking_for:
        fields.append(_field("Looking for", looking_for))

    # 2. Progress & bossing
    cb = cleaned(val("w_CB"))
    if cb:
        fields.append(_field("Clan Boss (one-key top chest)", cb))

    hydra = cleaned(val("w_hydra_diff"))
    hydra_clash_raw = val("w_hydra_clash")
    hydra_clash_fmt = _format_number(hydra_clash_raw) if hydra_clash_raw else ""
    hydra_parts: list[str] = []
    if hydra:
        hydra_parts.append(hydra)
    if hydra_clash_fmt:
        hydra_parts.append(f"Avg Hydra Clash: {hydra_clash_fmt}")
    if hydra_parts:
        fields.append(_field("Hydra • Avg Hydra Clash", " • ".join(hydra_parts)))

    chimera = cleaned(val("w_chimera_diff"))
    chimera_clash_raw = val("w_chimera_clash")
    chimera_clash_fmt = _format_number(chimera_clash_raw) if chimera_clash_raw else ""
    chimera_parts: list[str] = []
    if chimera:
        chimera_parts.append(chimera)
    if chimera_clash_fmt:
        chimera_parts.append(f"Avg Chimera Clash: {chimera_clash_fmt}")
    if chimera_parts:
        fields.append(_field("Chimera • Avg Chimera Clash", " • ".join(chimera_parts)))

    # 3. War modes
    # Siege participation is always rendered, even if “No”.
    siege_answer = (val("w_siege") or "").strip()
    if siege_answer:
        fields.append(_field("Siege participation", siege_answer))
    else:
        fields.append(_field("Siege participation", "No"))

    siege_detail = cleaned(val("w_siege_detail"))
    siege_participates = siege_answer and siege_answer.lower() not in {"", "no", "none"}
    if siege_participates and siege_detail:
        fields.append(_field("Siege setup", siege_detail))

    cvc_raw = (val("w_cvc") or "").strip()
    cvc_points_raw = val("w_cvc_points")
    cvc_priority = _map_cvc_priority(cvc_raw)
    cvc_points_fmt = _format_number(cvc_points_raw) if cvc_points_raw else ""
    cvc_parts: list[str] = []
    if cvc_priority:
        cvc_parts.append(f"CvC priority: {cvc_priority}")
    if cvc_points_fmt:
        cvc_parts.append(f"Minimum CvC points: {cvc_points_fmt}")
    if cvc_parts:
        fields.append(_field("CvC priority • Minimum CvC points", " • ".join(cvc_parts)))

    # 4. Notes
    progression = cleaned(val("w_level"))
    if progression:
        if len(progression) > 200:
            progression = progression[:197] + "..."
        fields.append(_field("Progression (self-feel)", progression))

    origin = cleaned(val("w_origin"))
    if origin:
        fields.append(_field("Heard about C1C from", origin))

    return fields


def _field(name: str, value: str) -> dict[str, Any]:
    if len(value) > 1024:
        value = f"{value[:1021]}..."
    return {"name": name, "value": value, "inline": False}


def _format_number(value: Any) -> str:
    """Format numbers as ### K / #.# M where appropriate."""

    try:
        if value is None:
            return ""
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        num = float(value)
    except Exception:
        return str(value).strip()

    if num < 1000:
        if num.is_integer():
            return f"{int(num)}"
        return f"{num:.0f}"

    if num < 1_000_000:
        short = num / 1000.0
        if short.is_integer():
            return f"{int(short)} K"
        return f"{short:.1f} K"

    short = num / 1_000_000.0
    if short.is_integer():
        return f"{int(short)} M"
    return f"{short:.1f} M"


def _map_cvc_priority(raw: str) -> str:
    mapping = {
        "1": "Low",
        "2": "Low-Medium",
        "3": "Medium",
        "4": "High-Medium",
        "5": "High",
    }
    value = (raw or "").strip()
    if not value:
        return ""
    if value in mapping:
        return mapping[value]
    return value


def _format_answer(qtype: str, stored: Any) -> str:
    """Format answers similar to the existing onboarding rendering."""

    if stored is None:
        return ""

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


__all__ = ["build_summary_embed"]
